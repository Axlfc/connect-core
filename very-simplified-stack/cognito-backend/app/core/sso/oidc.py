import logging
import time
from typing import Dict, Any, Optional, List
import jwt
from jwt.exceptions import PyJWTError, InvalidSignatureError, ExpiredSignatureError, InvalidTokenError
from jwt.algorithms import RSAAlgorithm, ECAlgorithm
import httpx

from app.core.sso.base import SSOProvider, SSOUserClaims

logger = logging.getLogger("cognito.backend.sso.oidc")


class InvalidTokenSignatureError(ValueError):
    """Excepción lanzada cuando la firma del ID Token es inválida o no se pudo verificar contra el JWKS."""
    pass


class OIDCProvider(SSOProvider):
    """
    Implementación real de OIDC (OpenID Connect) basada en OAuth 2.0 / JWT.
    Soporta verificación real de firmas asimétricas (RS256 / ES256) contra el JWKS del proveedor (Okta, Azure AD, Google, Mock IdP).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        issuer: str,
        authorization_endpoint: str,
        token_endpoint: str,
        jwks_uri: Optional[str] = None,
        jwks_data: Optional[Dict[str, Any]] = None,
        allowed_algorithms: Optional[List[str]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.issuer = issuer.rstrip("/") if issuer else ""
        self.authorization_endpoint = authorization_endpoint
        self.token_endpoint = token_endpoint
        self.jwks_uri = jwks_uri
        self.jwks_data = jwks_data or {}
        self.allowed_algorithms = allowed_algorithms or ["RS256", "ES256"]
        self._http_client = http_client

    def get_authorization_url(self, redirect_uri: str, state: str, scope: str = "openid profile email") -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
        query_string = str(httpx.QueryParams(params))
        return f"{self.authorization_endpoint}?{query_string}"

    async def process_callback(self, code: str, redirect_uri: str) -> SSOUserClaims:
        """
        Intercambia el código de autorización por tokens en el Token Endpoint del IdP
        y valida la firma del ID token retornado.
        """
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        if self._http_client:
            client = self._http_client
            close_client = False
        else:
            client = httpx.AsyncClient()
            close_client = True

        try:
            response = await client.post(self.token_endpoint, data=payload, headers={"Accept": "application/json"})
            if response.status_code != 200:
                raise ValueError(f"Error en intercambio de token con IdP ({response.status_code}): {response.text}")

            token_data = response.json()
            id_token = token_data.get("id_token")
            if not id_token:
                raise ValueError("Respuesta del IdP no contiene 'id_token'")

            claims_dict = self.validate_id_token(id_token)
            return self._map_claims_to_sso_user(claims_dict)
        finally:
            if close_client:
                await client.aclose()

    def validate_id_token(self, id_token: str, jwks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Valida la firma asimétrica (RS256 / ES256) del ID Token contra las claves públicas expuestas en el JWKS.
        Lanza InvalidTokenSignatureError si la firma está manipulada o es inválida.
        """
        effective_jwks = jwks or self.jwks_data
        if not effective_jwks and self.jwks_uri:
            # Si no se pasó jwks en memoria, descargar síncronamente desde jwks_uri
            try:
                with httpx.Client(timeout=5) as sync_client:
                    resp = sync_client.get(self.jwks_uri)
                    if resp.status_code == 200:
                        effective_jwks = resp.json()
            except Exception as e:
                logger.warning(f"No se pudo descargar JWKS desde {self.jwks_uri}: {e}")

        try:
            unverified_header = jwt.get_unverified_header(id_token)
        except PyJWTError as e:
            raise InvalidTokenSignatureError(f"Encabezado del JWT malformado o inválido: {e}") from e

        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg")

        if alg not in self.allowed_algorithms:
            raise InvalidTokenSignatureError(f"Algoritmo de firma '{alg}' no está en los algoritmos permitidos ({self.allowed_algorithms})")

        public_key = None
        if effective_jwks and "keys" in effective_jwks:
            for key_dict in effective_jwks["keys"]:
                if kid and key_dict.get("kid") == kid:
                    public_key = self._key_dict_to_public_key(key_dict)
                    break
                elif not kid and key_dict.get("alg") == alg:
                    public_key = self._key_dict_to_public_key(key_dict)
                    break

        if public_key is None:
            if isinstance(effective_jwks, dict) and "public_key_pem" in effective_jwks:
                public_key = effective_jwks["public_key_pem"]

        if public_key is None:
            raise InvalidTokenSignatureError(f"No se encontró clave pública válida en JWKS para kid='{kid}', alg='{alg}'")

        try:
            # Validación estricta de firma y claims
            decoded_claims = jwt.decode(
                id_token,
                key=public_key,
                algorithms=[alg],
                audience=self.client_id,
                issuer=self.issuer if self.issuer else None,
                options={
                    "verify_signature": True,
                    "verify_aud": True if self.client_id else False,
                    "verify_iss": True if self.issuer else False,
                    "verify_exp": True,
                },
            )
            return decoded_claims
        except InvalidSignatureError as e:
            raise InvalidTokenSignatureError(f"Firma del ID token manipulada o inválida: {e}") from e
        except ExpiredSignatureError as e:
            raise InvalidTokenSignatureError(f"ID token expirado: {e}") from e
        except InvalidTokenError as e:
            raise InvalidTokenSignatureError(f"Claims del ID token inválidos: {e}") from e
        except Exception as e:
            raise InvalidTokenSignatureError(f"Error validando ID token: {e}") from e

    def _key_dict_to_public_key(self, key_dict: Dict[str, Any]) -> Any:
        kty = key_dict.get("kty")
        if kty == "RSA":
            return RSAAlgorithm.from_jwk(key_dict)
        elif kty == "EC":
            return ECAlgorithm.from_jwk(key_dict)
        else:
            raise InvalidTokenSignatureError(f"Tipo de clave JWK no soportado: {kty}")

    def _map_claims_to_sso_user(self, claims: Dict[str, Any]) -> SSOUserClaims:
        subject = claims.get("sub") or claims.get("subject") or claims.get("oid") or ""
        email = claims.get("email") or claims.get("preferred_username") or claims.get("upn") or ""
        name = claims.get("name") or claims.get("displayName")
        if not name:
            fname = claims.get("given_name", "")
            lname = claims.get("family_name", "")
            if fname or lname:
                name = f"{fname} {lname}".strip()

        groups = claims.get("groups", []) or claims.get("roles", []) or claims.get("cognito:groups", [])
        roles = []
        if isinstance(groups, list):
            if any(g in ["Cognito-Admins", "admin", "org_admin"] for g in groups):
                roles.append("org_admin")
            if any(g in ["Cognito-Auditors", "auditor"] for g in groups):
                roles.append("auditor")

        if not roles:
            roles = ["developer"]

        return SSOUserClaims(
            subject=subject,
            email=email,
            full_name=name,
            roles=roles,
            raw_claims=claims,
        )

    async def logout(self, user_id: str) -> bool:
        logger.info(f"OIDCProvider: Cierre de sesión registrado para usuario '{user_id}'")
        return True
