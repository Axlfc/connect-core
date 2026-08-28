import os
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.core.sso import sso_manager, InvalidTokenSignatureError
from app.core.sso.service import sso_service
from app.core.audit import audit_logger, AuditLogRecord, ActorInfo

logger = logging.getLogger("cognito.backend.api.auth")

router = APIRouter(prefix="/auth/sso", tags=["SSO Authentication"])


class SSOLoginResponse(BaseModel):
    authorization_url: str
    state: str
    provider_type: str


class SSOCallbackResponse(BaseModel):
    session_id: str
    user_id: str
    org_id: str
    email: str
    full_name: Optional[str] = None
    roles: list[str]


class SSOLogoutRequest(BaseModel):
    user_id: str
    org_id: str
    session_id: Optional[str] = None


@router.get("/login", response_model=SSOLoginResponse)
async def sso_login(
    redirect_uri: str = Query(..., description="URI de redirección del cliente tras autenticarse con IdP"),
    org_id: Optional[str] = Query(None, description="ID de organización opcional"),
    provider_type: Optional[str] = Query(None, description="Tipo de proveedor ('oidc' o 'saml')"),
):
    state = f"st-{uuid.uuid4().hex[:12]}"
    provider = sso_manager.get_provider_for_org(org_id=org_id, provider_type=provider_type)
    auth_url = provider.get_authorization_url(redirect_uri=redirect_uri, state=state)
    eff_p_type = provider_type or os.getenv("COGNITO_SSO_PROVIDER", "oidc")

    return SSOLoginResponse(
        authorization_url=auth_url,
        state=state,
        provider_type=eff_p_type,
    )


@router.get("/callback", response_model=SSOCallbackResponse)
@router.post("/callback", response_model=SSOCallbackResponse)
async def sso_callback(
    request: Request,
    code: Optional[str] = Query(None),
    redirect_uri: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    provider_type: Optional[str] = Query(None),
):
    # Procesa tanto query params como JSON body si se envió vía POST
    if request.method == "POST":
        try:
            body = await request.json()
            code = code or body.get("code")
            redirect_uri = redirect_uri or body.get("redirect_uri")
            org_id = org_id or body.get("org_id")
            session_id = session_id or body.get("session_id")
            provider_type = provider_type or body.get("provider_type")
        except Exception:
            pass

    if not code or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requieren 'code' y 'redirect_uri' para procesar el callback SSO",
        )

    provider = sso_manager.get_provider_for_org(org_id=org_id, provider_type=provider_type)

    try:
        claims = await provider.process_callback(code=code, redirect_uri=redirect_uri)
    except InvalidTokenSignatureError as e:
        logger.warning(f"Rechazado intento de login SSO con firma inválida: {e}")
        audit_logger.record(
            AuditLogRecord(
                audit_id=f"aud-sso-err-{uuid.uuid4().hex[:12]}",
                org_id=org_id or "org-default-local",
                action="auth.sso_login",
                resource="sso:callback",
                status="INVALID_SIGNATURE",
                actor=ActorInfo(type="user", id="anonymous_unverified"),
                details={"error": str(e)},
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firma de token SSO inválida o manipulada: {e}",
        )
    except Exception as e:
        logger.error(f"Error procesando callback SSO: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al autenticar con el proveedor SSO: {e}",
        )

    # Auto-aprovisionamiento y mapeo por dominio de email
    target_org_id = sso_service.resolve_org_id_for_email(claims.email, explicit_org_id=org_id)
    user = sso_service.provision_or_update_user(claims, org_id=target_org_id)

    # Emisión/vinculación de sesión Cognito
    cognito_session_id = sso_service.bind_or_create_cognito_session(
        user=user,
        existing_session_id=session_id,
    )

    # Auditoría SIEM
    sso_service.record_sso_login_audit(user=user, session_id=cognito_session_id, status="SUCCESS")

    return SSOCallbackResponse(
        session_id=cognito_session_id,
        user_id=user.user_id,
        org_id=user.org_id,
        email=user.email,
        full_name=user.full_name,
        roles=user.roles or ["developer"],
    )


@router.post("/logout")
async def sso_logout(payload: SSOLogoutRequest):
    provider = sso_manager.get_provider_for_org(org_id=payload.org_id)
    await provider.logout(user_id=payload.user_id)

    sso_service.record_sso_logout_audit(
        user_id=payload.user_id,
        org_id=payload.org_id,
        session_id=payload.session_id,
    )

    return {"message": "Sesión SSO cerrada correctamente", "user_id": payload.user_id}
