import os
from sqlalchemy import Column, String, Integer, Float, Boolean, JSON
from app.core.database import Base
import time

import sys
is_testing = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
TABLE_ARGS = {} if is_testing else {"schema": "cognito"}

class DBTask(Base):
    __tablename__ = "tasks"
    __table_args__ = TABLE_ARGS

    task_id = Column(String(50), primary_key=True)
    session_id = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    requirements = Column(String, nullable=False)
    status = Column(String(50), default="pending")
    context = Column(JSON, nullable=False)
    route_decision = Column(JSON, nullable=True)
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)

class DBRouteDecision(Base):
    __tablename__ = "route_decisions"
    __table_args__ = TABLE_ARGS

    decision_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), nullable=True)
    executor = Column(String(50), nullable=False)
    logical_tier = Column(String(50), nullable=False)
    resolved_model_identifier = Column(String(255), nullable=False)
    reasoning_effort = Column(String(50), nullable=True)
    mode = Column(String(50), nullable=False)
    risk = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    execution_policy = Column(JSON, nullable=False)
    reasons = Column(JSON, nullable=False)
    execution_constraints = Column(JSON, nullable=False)
    verification_requirements = Column(JSON, nullable=False)
    fallback_chain = Column(JSON, nullable=False)
    timestamp = Column(Float, default=time.time)

class DBExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = TABLE_ARGS

    attempt_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    route_decision = Column(JSON, nullable=False)
    worktree_path = Column(String(1024), nullable=False)
    status = Column(String(50), nullable=False)
    patch = Column(String, nullable=True)
    changed_files = Column(JSON, nullable=False)
    verification = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    started_at = Column(Float, default=time.time)
    ended_at = Column(Float, nullable=True)

class DBApprovalRequest(Base):
    __tablename__ = "approvals"
    __table_args__ = TABLE_ARGS

    approval_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), nullable=False)
    attempt_id = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    description = Column(String, nullable=False)
    details = Column(JSON, nullable=False)
    status = Column(String(50), default="pending")
    created_at = Column(Float, default=time.time)
    decided_at = Column(Float, nullable=True)
    response_reason = Column(String, nullable=True)

class DBVerificationRun(Base):
    __tablename__ = "verification_runs"
    __table_args__ = TABLE_ARGS

    run_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), nullable=False)
    attempt_id = Column(String(50), nullable=False)
    commands_executed = Column(JSON, nullable=False)
    exit_status = Column(Integer, nullable=False)
    duration_sec = Column(Float, nullable=False)
    stdout = Column(String, nullable=False)
    stderr = Column(String, nullable=False)
    changed_diagnostics = Column(JSON, nullable=True)
    failed_tests = Column(JSON, nullable=False)
    failure_classification = Column(String(50), nullable=True)
    timestamp = Column(Float, default=time.time)

class DBEscalationRecord(Base):
    __tablename__ = "escalations"
    __table_args__ = TABLE_ARGS

    escalation_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), nullable=False)
    previous_attempt_id = Column(String(50), nullable=False)
    previous_tier = Column(String(50), nullable=False)
    new_tier = Column(String(50), nullable=False)
    escalation_reason = Column(String, nullable=False)
    failure_classification = Column(String(50), nullable=False)
    timestamp = Column(Float, default=time.time)

class DBAuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = TABLE_ARGS

    event_id = Column(String(50), primary_key=True)
    task_id = Column(String(50), nullable=True)
    session_id = Column(String(50), nullable=True)
    origin = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)
    description = Column(String, nullable=False)
    metadata_fields = Column(JSON, name="metadata", nullable=False)
    timestamp = Column(Float, default=time.time)

class DBOutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = TABLE_ARGS

    event_id = Column(String(50), primary_key=True)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    is_delivered = Column(Boolean, default=False)
    timestamp = Column(Float, default=time.time)

class DBOrganization(Base):
    __tablename__ = "organizations"
    __table_args__ = TABLE_ARGS

    org_id = Column(String(64), primary_key=True)
    slug = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    status = Column(String(32), default="active", nullable=False)
    sso_enabled = Column(Boolean, default=False, nullable=False)
    sso_provider_config = Column(JSON, nullable=True)
    created_at = Column(Float, default=time.time, nullable=False)
    updated_at = Column(Float, default=time.time, nullable=False)

class DBProject(Base):
    __tablename__ = "projects"
    __table_args__ = TABLE_ARGS

    project_id = Column(String(64), primary_key=True)
    org_id = Column(String(64), nullable=False)
    slug = Column(String(64), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    status = Column(String(32), default="active", nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)

class DBUser(Base):
    __tablename__ = "users"
    __table_args__ = TABLE_ARGS

    user_id = Column(String(64), primary_key=True)
    org_id = Column(String(64), nullable=False)
    email = Column(String(255), nullable=False)
    external_subject_id = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    status = Column(String(32), default="active", nullable=False)
    roles = Column(JSON, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)
    last_login_at = Column(Float, nullable=True)

class DBSession(Base):
    __tablename__ = "sessions"
    __table_args__ = TABLE_ARGS

    session_id = Column(String(64), primary_key=True)
    org_id = Column(String(64), nullable=True)
    project_id = Column(String(64), nullable=True)
    user_id = Column(String(64), nullable=True)
    auth_type = Column(String(32), default="anonymous", nullable=False)
    status = Column(String(32), default="active", nullable=False)
    cwd = Column(String(1024), nullable=False)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    approval_timeout_seconds = Column(Integer, nullable=True)
    blocked_actions_count = Column(Integer, default=0, nullable=False)
    approval_summary = Column(JSON, default=list, nullable=False)
    metadata_fields = Column(JSON, name="metadata", default=dict, nullable=False)

class DBSessionMessage(Base):
    __tablename__ = "session_messages"
    __table_args__ = TABLE_ARGS

    message_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    type = Column(String(32), default="message", nullable=False)
    role = Column(String(32), nullable=True)
    content = Column(String, nullable=True)
    tool_name = Column(String(255), nullable=True)
    tool_call_id = Column(String(255), nullable=True)
    tool_calls = Column(JSON, nullable=True)
    summary = Column(String, nullable=True)
    covers_through_line = Column(Integer, nullable=True)
    context_ledger = Column(JSON, nullable=True)
    delivered = Column(Boolean, default=False, nullable=True)
    steering_id = Column(String(64), nullable=True)
    ts = Column(String(64), nullable=False)


class DBStructuredAuditLog(Base):
    __tablename__ = "structured_audit_logs"
    __table_args__ = TABLE_ARGS

    audit_id = Column(String(64), primary_key=True)
    timestamp = Column(String(64), nullable=False, index=True)
    org_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), nullable=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    actor = Column(JSON, nullable=False)
    action = Column(String(255), nullable=False)
    resource = Column(String(1024), nullable=False)
    trace_id = Column(String(64), nullable=False, index=True)
    request_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False)
    approval_metadata = Column(JSON, nullable=True)
    security_context = Column(JSON, nullable=True)
    raw_payload = Column(JSON, nullable=False)
