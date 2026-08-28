from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class SSOUserClaims(BaseModel):
    subject: str
    email: str
    full_name: Optional[str] = None
    roles: list[str] = Field(default_factory=lambda: ["developer"])
    raw_claims: Dict[str, Any] = Field(default_factory=dict)


class SSOProvider(ABC):
    """
    Abstract interface for SSO Authentication Providers (OIDC, SAML).
    """

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        Generates the authorization URL to redirect the user to the IdP.
        """
        pass

    @abstractmethod
    async def process_callback(self, code: str, redirect_uri: str) -> SSOUserClaims:
        """
        Handles authorization code exchange callback and returns validated user claims.
        """
        pass

    @abstractmethod
    def validate_id_token(self, id_token: str, jwks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validates the signature and claims of an ID token against JWKS.
        Lanzará InvalidTokenSignatureError / ValueError si la firma o los claims son inválidos.
        """
        pass

    @abstractmethod
    async def logout(self, user_id: str) -> bool:
        """
        Executes logout logic for the SSO session.
        """
        pass
