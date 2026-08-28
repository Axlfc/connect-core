import os
import json
import time
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from app.core.sso.base import SSOUserClaims
from app.core.session_manager import SessionManager
from app.core.audit import audit_logger, AuditLogRecord, ActorInfo
from app.core.database import get_db_sync_session
from app.models.db import DBOrganization, DBUser, DBSession

logger = logging.getLogger("cognito.backend.sso.service")

# Global domain mapping default rule (can be overridden via env var COGNITO_SSO_DOMAIN_MAP JSON or Org config)
def get_domain_mapping() -> Dict[str, str]:
    raw = os.getenv("COGNITO_SSO_DOMAIN_MAP", "")
    if raw.strip():
        try:
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Could not parse COGNITO_SSO_DOMAIN_MAP: {e}")
    return {}


class SSOService:
    """
    SSO Orchestration Service.
    - Maps SSO claims to User/Organization based on email domain rules.
    - Auto-provisions new users or updates existing users in DB.
    - Binds/issues Cognito sessions via SessionManager (reusing existing session mechanism).
    - Emits structured audit logs for login/logout events.
    """

    def __init__(self, session_manager: Optional[SessionManager] = None):
        self.session_manager = session_manager or SessionManager()

    def resolve_org_id_for_email(self, email: str, explicit_org_id: Optional[str] = None) -> str:
        if explicit_org_id:
            return explicit_org_id

        domain_map = get_domain_mapping()
        if "@" in email:
            domain = email.split("@")[-1].lower()
            if domain in domain_map:
                return domain_map[domain]

        return "org-default-local"

    def ensure_organization_exists(self, org_id: str) -> DBOrganization:
        db = get_db_sync_session()
        try:
            org = db.query(DBOrganization).filter(DBOrganization.org_id == org_id).first()
            if not org:
                slug = org_id.replace("org-", "").lower()
                org = DBOrganization(
                    org_id=org_id,
                    slug=slug,
                    display_name=f"Organization {slug.capitalize()}",
                    status="active",
                    sso_enabled=True,
                    created_at=time.time(),
                    updated_at=time.time(),
                )
                db.add(org)
                db.commit()
                db.refresh(org)
            return org
        finally:
            db.close()

    def provision_or_update_user(self, claims: SSOUserClaims, org_id: str) -> DBUser:
        self.ensure_organization_exists(org_id)
        db = get_db_sync_session()
        now = time.time()
        try:
            user = None
            if claims.email:
                user = db.query(DBUser).filter(DBUser.org_id == org_id, DBUser.email == claims.email).first()
            if not user and claims.subject:
                user = db.query(DBUser).filter(DBUser.org_id == org_id, DBUser.external_subject_id == claims.subject).first()

            if user:
                # Update user fields
                user.external_subject_id = claims.subject or user.external_subject_id
                if claims.full_name:
                    user.full_name = claims.full_name
                if claims.roles:
                    user.roles = claims.roles
                user.last_login_at = now
                db.commit()
                db.refresh(user)
                logger.info(f"SSOService: User '{user.email}' ({user.user_id}) updated upon SSO login.")
            else:
                # Auto-provision new user on first login
                user_id = f"usr-{uuid.uuid4().hex[:12]}"
                user = DBUser(
                    user_id=user_id,
                    org_id=org_id,
                    email=claims.email,
                    external_subject_id=claims.subject,
                    full_name=claims.full_name or claims.email.split("@")[0],
                    status="active",
                    roles=claims.roles or ["developer"],
                    created_at=now,
                    last_login_at=now,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"SSOService: Auto-provisioned new user '{user.email}' ({user.user_id}) for Org '{org_id}'.")

            return user
        finally:
            db.close()

    def bind_or_create_cognito_session(
        self,
        user: DBUser,
        cwd: Optional[str] = None,
        existing_session_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> str:
        eff_cwd = cwd or os.getcwd()
        if existing_session_id:
            try:
                meta = self.session_manager.open(existing_session_id)
                session_id = existing_session_id
            except FileNotFoundError:
                session_id = self.session_manager.create(
                    cwd=eff_cwd,
                    org_id=user.org_id,
                    project_id=project_id,
                    user_id=user.user_id,
                )
        else:
            session_id = self.session_manager.create(
                cwd=eff_cwd,
                org_id=user.org_id,
                project_id=project_id,
                user_id=user.user_id,
            )

        now_str = datetime.now(timezone.utc).isoformat()
        # Ensure DBSession table row exists/is updated
        db = get_db_sync_session()
        try:
            sess_row = db.query(DBSession).filter(DBSession.session_id == session_id).first()
            if not sess_row:
                sess_row = DBSession(
                    session_id=session_id,
                    org_id=user.org_id,
                    project_id=project_id,
                    user_id=user.user_id,
                    auth_type="authenticated_sso",
                    status="active",
                    cwd=eff_cwd,
                    created_at=now_str,
                    updated_at=now_str,
                    message_count=0,
                )
                db.add(sess_row)
            else:
                sess_row.org_id = user.org_id
                sess_row.user_id = user.user_id
                sess_row.auth_type = "authenticated_sso"
                if project_id:
                    sess_row.project_id = project_id
                sess_row.updated_at = now_str
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed updating DBSession row multi-tenant binding: {e}")
        finally:
            db.close()

        # Update session metadata file/dict
        try:
            meta_dict = self.session_manager._read_session_meta(session_id) or {}
            meta_dict["org_id"] = user.org_id
            meta_dict["user_id"] = user.user_id
            if project_id:
                meta_dict["project_id"] = project_id
            self.session_manager._write_session_meta(session_id, meta_dict)
        except Exception as e:
            logger.warning(f"Failed updating session meta dict: {e}")

        return session_id

    def record_sso_login_audit(
        self,
        user: DBUser,
        session_id: str,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogRecord:
        record = AuditLogRecord(
            audit_id=f"aud-sso-{uuid.uuid4().hex[:12]}",
            org_id=user.org_id,
            user_id=user.user_id,
            session_id=session_id,
            action="auth.sso_login",
            resource=f"sso:{user.email}",
            status=status,
            actor=ActorInfo(
                type="user",
                id=user.user_id,
                user_id=user.user_id,
                org_id=user.org_id,
                email=user.email,
            ),
            details=details or {"email": user.email, "roles": user.roles},
        )
        return audit_logger.record(record)

    def record_sso_logout_audit(
        self,
        user_id: str,
        org_id: str,
        email: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AuditLogRecord:
        record = AuditLogRecord(
            audit_id=f"aud-sso-{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            user_id=user_id,
            session_id=session_id,
            action="auth.sso_logout",
            resource=f"sso:{email or user_id}",
            status="SUCCESS",
            actor=ActorInfo(
                type="user",
                id=user_id,
                user_id=user_id,
                org_id=org_id,
                email=email,
            ),
            details={"logout_timestamp": time.time()},
        )
        return audit_logger.record(record)


sso_service = SSOService()
