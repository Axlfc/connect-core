import os
import logging
from typing import Dict, Any, Optional

from app.core.sso.base import SSOProvider
from app.core.sso.oidc import OIDCProvider
from app.core.sso.saml import SAMLProvider

logger = logging.getLogger("cognito.backend.sso.manager")


class SSOManager:
    """
    Central SSO Manager to resolve and instantiate SSO Providers (OIDC, SAML)
    dynamically based on Organization configuration or global environment defaults.
    """

    def __init__(self):
        self._providers: Dict[str, SSOProvider] = {}

    def get_provider_for_org(
        self,
        org_id: Optional[str] = None,
        provider_type: Optional[str] = None,
        org_sso_config: Optional[Dict[str, Any]] = None,
    ) -> SSOProvider:
        """
        Resolves the appropriate SSOProvider for a given Organization or system default.
        Layered resolution:
          1. Explicit provider_type or org_sso_config parameter
          2. Environment variable COGNITO_SSO_PROVIDER ("oidc" default, or "saml")
        """
        config = org_sso_config or {}
        p_type = (provider_type or config.get("type") or os.getenv("COGNITO_SSO_PROVIDER", "oidc")).lower()

        if p_type == "saml":
            return SAMLProvider(
                entity_id=config.get("entity_id"),
                sso_url=config.get("sso_url"),
                x509_cert=config.get("x509_cert"),
            )

        # OIDC default
        client_id = config.get("client_id") or os.getenv("COGNITO_OIDC_CLIENT_ID", "cognito-client-id")
        client_secret = config.get("client_secret") or os.getenv("COGNITO_OIDC_CLIENT_SECRET", "cognito-client-secret")
        issuer = config.get("issuer") or os.getenv("COGNITO_OIDC_ISSUER", "https://auth.example.com")
        auth_endpoint = config.get("authorization_endpoint") or os.getenv("COGNITO_OIDC_AUTH_URL", f"{issuer}/oauth2/v1/authorize")
        token_endpoint = config.get("token_endpoint") or os.getenv("COGNITO_OIDC_TOKEN_URL", f"{issuer}/oauth2/v1/token")
        jwks_uri = config.get("jwks_uri") or os.getenv("COGNITO_OIDC_JWKS_URI", f"{issuer}/oauth2/v1/keys")
        jwks_data = config.get("jwks_data")

        return OIDCProvider(
            client_id=client_id,
            client_secret=client_secret,
            issuer=issuer,
            authorization_endpoint=auth_endpoint,
            token_endpoint=token_endpoint,
            jwks_uri=jwks_uri,
            jwks_data=jwks_data,
        )


sso_manager = SSOManager()
