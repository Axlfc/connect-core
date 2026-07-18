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
