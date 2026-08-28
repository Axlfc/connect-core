import os
import json
import time
import pytest
import jwt
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from app.main import app
from app.core.sso import OIDCProvider, SAMLProvider, InvalidTokenSignatureError, sso_manager
from app.core.sso.service import sso_service
from app.core.audit import audit_logger
from app.core.database import get_db_sync_session
from app.models.db import DBUser, DBOrganization, DBSession

client = TestClient(app)


def generate_rsa_key_pair():
    """Helper for generating RSA private/public keys and JWKS dictionary."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Export JWK dictionary format using PyJWT
    jwk_dict = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = "test-key-1"
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"

    jwks_data = {"keys": [jwk_dict], "public_key_pem": public_pem.decode("utf-8")}
    return private_pem, jwks_data


@pytest.fixture
def mock_oidc_setup(monkeypatch):
    private_pem, jwks_data = generate_rsa_key_pair()
    issuer = "https://mock-idp.example.com"
    client_id = "test-cognito-client"
    client_secret = "test-cognito-secret"

    provider = OIDCProvider(
        client_id=client_id,
        client_secret=client_secret,
        issuer=issuer,
        authorization_endpoint=f"{issuer}/oauth2/v1/authorize",
        token_endpoint=f"{issuer}/oauth2/v1/token",
        jwks_data=jwks_data,
    )

    def mock_get_provider_for_org(org_id=None, provider_type=None, org_sso_config=None):
        if provider_type == "saml":
            return SAMLProvider()
        return provider

    monkeypatch.setattr(sso_manager, "get_provider_for_org", mock_get_provider_for_org)

    return {
        "private_pem": private_pem,
        "jwks_data": jwks_data,
        "issuer": issuer,
        "client_id": client_id,
        "provider": provider,
    }


def test_oidc_authorization_url_generation(mock_oidc_setup):
    provider = mock_oidc_setup["provider"]
    url = provider.get_authorization_url(redirect_uri="http://localhost:3000/callback", state="state123")
    assert "https://mock-idp.example.com/oauth2/v1/authorize" in url
    assert "client_id=test-cognito-client" in url
    assert "state=state123" in url


def test_oidc_valid_id_token_verification(mock_oidc_setup):
    private_pem = mock_oidc_setup["private_pem"]
    provider = mock_oidc_setup["provider"]

    now = int(time.time())
    valid_payload = {
        "sub": "user-sub-12345",
        "email": "alice@acme.com",
        "name": "Alice Enterprise",
        "iss": mock_oidc_setup["issuer"],
        "aud": mock_oidc_setup["client_id"],
        "exp": now + 3600,
        "iat": now,
        "groups": ["Cognito-Admins"],
    }

    id_token = jwt.encode(
        valid_payload,
        key=private_pem,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )

    claims = provider.validate_id_token(id_token)
    assert claims["sub"] == "user-sub-12345"
    assert claims["email"] == "alice@acme.com"


def test_oidc_tampered_signature_token_rejected(mock_oidc_setup):
    """
    CRITERIO DE ACEPTACIÓN EXPLÍCITO:
    Un token con firma manipulada es rechazado y lanza InvalidTokenSignatureError.
    """
    private_pem = mock_oidc_setup["private_pem"]
    provider = mock_oidc_setup["provider"]

    now = int(time.time())
    valid_payload = {
        "sub": "user-sub-12345",
        "email": "attacker@evil.com",
        "iss": mock_oidc_setup["issuer"],
        "aud": mock_oidc_setup["client_id"],
        "exp": now + 3600,
    }

    id_token = jwt.encode(
        valid_payload,
        key=private_pem,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )

    # Manipula la firma o los datos del token
    header, payload, signature = id_token.split(".")
    tampered_payload_str = payload[:-2] + ("AA" if payload[-1] != "A" else "BB")
    tampered_id_token = f"{header}.{tampered_payload_str}.{signature}"

    with pytest.raises(InvalidTokenSignatureError) as exc_info:
        provider.validate_id_token(tampered_id_token)

    assert "Firma" in str(exc_info.value) or "inválida" in str(exc_info.value) or "Claims" in str(exc_info.value) or "malformado" in str(exc_info.value)


@pytest.mark.asyncio
async def test_oidc_end_to_end_callback_flow_and_auto_provisioning(mock_oidc_setup, respx_mock):
    private_pem = mock_oidc_setup["private_pem"]
    token_url = f"{mock_oidc_setup['issuer']}/oauth2/v1/token"

    now = int(time.time())
    id_token_payload = {
        "sub": "sub-bob-999",
        "email": "bob@acme-corp.com",
        "name": "Bob Builder",
        "iss": mock_oidc_setup["issuer"],
        "aud": mock_oidc_setup["client_id"],
        "exp": now + 3600,
        "roles": ["developer"],
    }

    mock_id_token = jwt.encode(
        id_token_payload,
        key=private_pem,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )

    # Mock Token Endpoint
    respx_mock.post(token_url).respond(
        status_code=200,
        json={
            "access_token": "mock-access-token",
            "id_token": mock_id_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    # Configure domain mapping for acme-corp.com -> org-acme-corp
    os.environ["COGNITO_SSO_DOMAIN_MAP"] = json.dumps({"acme-corp.com": "org-acme-corp"})

    response = client.get(
        "/api/auth/sso/callback",
        params={
            "code": "auth-code-12345",
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "bob@acme-corp.com"
    assert data["org_id"] == "org-acme-corp"
    assert data["session_id"] is not None

    # Verify User auto-provisioned in DB
    db = get_db_sync_session()
    try:
        user = db.query(DBUser).filter(DBUser.email == "bob@acme-corp.com").first()
        assert user is not None
        assert user.org_id == "org-acme-corp"
        assert user.external_subject_id == "sub-bob-999"

        # Verify Session multi-tenant binding
        sess = db.query(DBSession).filter(DBSession.session_id == data["session_id"]).first()
        assert sess is not None
        assert sess.user_id == user.user_id
        assert sess.org_id == "org-acme-corp"
        assert sess.auth_type == "authenticated_sso"
    finally:
        db.close()

    # Verify Audit Log event registered
    records = audit_logger.get_records(session_id=data["session_id"])
    sso_events = [r for r in records if r.action == "auth.sso_login"]
    assert len(sso_events) > 0
    assert sso_events[0].status == "SUCCESS"
    assert sso_events[0].user_id == user.user_id


def test_sso_logout_endpoint_and_audit(mock_oidc_setup):
    response = client.post(
        "/api/auth/sso/logout",
        json={
            "user_id": "usr-test-logout",
            "org_id": "org-test-logout",
            "session_id": "sess-logout-123",
        },
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == "usr-test-logout"

    # Verify Audit Log event registered
    records = audit_logger.get_records(session_id="sess-logout-123")
    logout_events = [r for r in records if r.action == "auth.sso_logout"]
    assert len(logout_events) > 0
    assert logout_events[0].status == "SUCCESS"


def test_saml_provider_stub_instantiation_and_callback():
    saml_p = SAMLProvider(entity_id="https://idp.saml.example.com", sso_url="https://idp.saml.example.com/sso")
    auth_url = saml_p.get_authorization_url(redirect_uri="http://localhost:3000/callback", state="st123")
    assert "https://idp.saml.example.com/sso" in auth_url

    response = client.get(
        "/api/auth/sso/callback",
        params={
            "code": "saml-code-123",
            "redirect_uri": "http://localhost:3000/callback",
            "provider_type": "saml",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "saml.user@example.com"
    assert data["session_id"] is not None
