import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.core.secrets import (
    LocalFileSecretsProvider,
    VaultSecretsProvider,
    get_secrets_provider,
    reset_secrets_provider,
)
from app.services.mcp_server import verify_mcp_auth
from app.api.routes.ai_agents import secrets_reload_rate_limiter


@pytest.fixture(autouse=True)
def clean_secrets_state():
    reset_secrets_provider(None)
    secrets_reload_rate_limiter.reset()
    yield
    reset_secrets_provider(None)
    secrets_reload_rate_limiter.reset()


def test_local_file_secrets_provider_auto_generation(tmp_path, monkeypatch):
    monkeypatch.delenv("COGNITO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("COGNITO_API_KEY", raising=False)
    monkeypatch.delenv("COGNITO_SECRETS_PROVIDER", raising=False)

    fake_config_file = tmp_path / "cognito" / "config.json"
    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=0.0)

    token = provider.get_secret("AuthToken")
    assert token is not None
    assert len(token) > 0
    assert fake_config_file.exists()

    # Permissions check
    assert (fake_config_file.stat().st_mode & 0o777) == 0o600
    assert (fake_config_file.parent.stat().st_mode & 0o777) == 0o700

    persisted_data = json.loads(fake_config_file.read_text(encoding="utf-8"))
    assert persisted_data.get("AuthToken") == token


def test_local_file_secrets_provider_env_override(tmp_path, monkeypatch):
    fake_config_file = tmp_path / "cognito" / "config.json"
    fake_config_file.parent.mkdir(parents=True, exist_ok=True)
    fake_config_file.write_text(json.dumps({"AuthToken": "file_token_123"}))

    monkeypatch.setenv("COGNITO_AUTH_TOKEN", "env_override_token_456")

    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=0.0)
    assert provider.get_secret("AuthToken") == "env_override_token_456"


def test_secret_rotation_and_revocation_flow(tmp_path, monkeypatch):
    monkeypatch.delenv("COGNITO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("COGNITO_API_KEY", raising=False)

    fake_config_file = tmp_path / "cognito" / "config.json"
    fake_config_file.parent.mkdir(parents=True, exist_ok=True)
    fake_config_file.write_text(json.dumps({"AuthToken": "initial_secret_v1"}))

    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=60.0)
    reset_secrets_provider(provider)

    # Initial token verification
    assert provider.get_secret("AuthToken") == "initial_secret_v1"
    assert verify_mcp_auth("initial_secret_v1") is True
    assert verify_mcp_auth("initial_secret_v2") is False

    # Simulate external rotation in config file
    fake_config_file.write_text(json.dumps({"AuthToken": "initial_secret_v2"}))

    # Before invalidation, cached value is returned
    assert provider.get_secret("AuthToken") == "initial_secret_v1"
    assert verify_mcp_auth("initial_secret_v1") is True

    # Invalidate secrets
    provider.invalidate("AuthToken")

    # After invalidation, old token is revoked/invalid, new token is required
    assert provider.get_secret("AuthToken") == "initial_secret_v2"
    assert verify_mcp_auth("initial_secret_v1") is False
    assert verify_mcp_auth("initial_secret_v2") is True


def test_vault_secrets_provider_stub(monkeypatch):
    monkeypatch.setenv("COGNITO_SECRETS_PROVIDER", "vault")
    reset_secrets_provider(None)

    provider = get_secrets_provider()
    assert isinstance(provider, VaultSecretsProvider)

    monkeypatch.setenv("VAULT_SECRET_AUTHTOKEN", "vault_token_789")
    assert provider.get_secret("AuthToken") == "vault_token_789"


def test_secrets_reload_unauthenticated_rejected(tmp_path, monkeypatch):
    fake_config_file = tmp_path / "cognito" / "config.json"
    fake_config_file.parent.mkdir(parents=True, exist_ok=True)
    fake_config_file.write_text(json.dumps({"AuthToken": "valid_token_123"}))

    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=300.0)
    reset_secrets_provider(provider)

    client = TestClient(app)
    # No auth header or body token
    response = client.post("/api/secrets/reload", json={"name": "AuthToken"})
    assert response.status_code == 401
    assert "Authentication failed" in response.json()["detail"]


def test_secrets_reload_invalid_token_rejected(tmp_path, monkeypatch):
    fake_config_file = tmp_path / "cognito" / "config.json"
    fake_config_file.parent.mkdir(parents=True, exist_ok=True)
    fake_config_file.write_text(json.dumps({"AuthToken": "valid_token_123"}))

    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=300.0)
    reset_secrets_provider(provider)

    client = TestClient(app)
    # Invalid Bearer token
    response = client.post(
        "/api/secrets/reload",
        headers={"Authorization": "Bearer wrong_token_456"},
        json={"name": "AuthToken"}
    )
    assert response.status_code == 401
    assert "Authentication failed" in response.json()["detail"]


def test_secrets_reload_api_endpoint(tmp_path, monkeypatch):
    fake_config_file = tmp_path / "cognito" / "config.json"
    fake_config_file.parent.mkdir(parents=True, exist_ok=True)
    fake_config_file.write_text(json.dumps({"AuthToken": "token_before_api_reload"}))

    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=300.0)
    reset_secrets_provider(provider)

    assert provider.get_secret("AuthToken") == "token_before_api_reload"

    # External rotation
    fake_config_file.write_text(json.dumps({"AuthToken": "token_after_api_reload"}))

    client = TestClient(app)
    # Authenticated call with Bearer header using active token
    response = client.post(
        "/api/secrets/reload",
        headers={"Authorization": "Bearer token_before_api_reload"},
        json={"name": "AuthToken"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"

    # Check that new secret is active
    assert provider.get_secret("AuthToken") == "token_after_api_reload"
    assert verify_mcp_auth("token_after_api_reload") is True
    assert verify_mcp_auth("token_before_api_reload") is False


def test_secrets_reload_rate_limiting(tmp_path, monkeypatch):
    fake_config_file = tmp_path / "cognito" / "config.json"
    fake_config_file.parent.mkdir(parents=True, exist_ok=True)
    fake_config_file.write_text(json.dumps({"AuthToken": "valid_token_rate_limit"}))

    provider = LocalFileSecretsProvider(config_path=fake_config_file, ttl_seconds=300.0)
    reset_secrets_provider(provider)

    client = TestClient(app)
    # 5 requests should succeed (200 OK)
    for i in range(5):
        res = client.post(
            "/api/secrets/reload",
            headers={"Authorization": "Bearer valid_token_rate_limit"},
            json={"name": "AuthToken"}
        )
        assert res.status_code == 200

    # 6th request should be rejected with 429 Too Many Requests
    res_overflow = client.post(
        "/api/secrets/reload",
        headers={"Authorization": "Bearer valid_token_rate_limit"},
        json={"name": "AuthToken"}
    )
    assert res_overflow.status_code == 429
    assert "Rate limit exceeded" in res_overflow.json()["detail"]
