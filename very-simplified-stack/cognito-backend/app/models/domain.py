from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
import uuid
import time

# ══════════════════════════════════════════════════════════════════════════════
# Repository and Editor Contexts
# ══════════════════════════════════════════════════════════════════════════════

class RepositoryContext(BaseModel):
    repository_id: str
    root_path: str
    current_branch: str
    base_commit: str
    is_dirty: bool
    changed_files_count: int
    repository_size_estimate_kb: Optional[int] = None
    detected_technologies: List[str] = Field(default_factory=list)
    has_agents_md: bool = False

class EditorContext(BaseModel):
    workspace_folder: str
    active_file: Optional[str] = None
    selected_language: Optional[str] = None
    selected_text_size: Optional[int] = None
    diagnostics_summary: Optional[Dict[str, Any]] = None
    git_status_summary: Optional[str] = None

class TaskContext(BaseModel):
    repository: RepositoryContext
    editor: EditorContext
    user_task: str
    sensitive_path_indicators: List[str] = Field(default_factory=list)
    test_framework_indicators: List[str] = Field(default_factory=list)
    task_history_indicators: List[str] = Field(default_factory=list)

# ══════════════════════════════════════════════════════════════════════════════
# Route and Execution Policies
# ══════════════════════════════════════════════════════════════════════════════

class SandboxPolicy(BaseModel):
    allowed_writable_roots: List[str] = Field(default_factory=list)
    read_only: bool = False

class NetworkPolicy(BaseModel):
    allowed_hosts: List[str] = Field(default_factory=list)
    allow_all: bool = False

class ApprovalPolicy(BaseModel):
    require_approval_for_shell: bool = True
    require_approval_for_write: bool = False
    require_approval_for_destructive: bool = True

class ExecutionPolicy(BaseModel):
    sandbox: SandboxPolicy = Field(default_factory=SandboxPolicy)
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)
    approval: ApprovalPolicy = Field(default_factory=ApprovalPolicy)

class RouteDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"route-{uuid.uuid4().hex[:12]}")
    executor: Literal["Ollama", "Codex"]
    logical_tier: Literal["local", "luna", "terra", "sol"]
    resolved_model_identifier: str
    reasoning_effort: Optional[str] = None
    mode: Literal["read", "plan", "act", "review"]
    risk: Literal["low", "medium", "high"]
    confidence: float
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    reasons: List[str] = Field(default_factory=list)
    execution_constraints: List[str] = Field(default_factory=list)
    verification_requirements: List[str] = Field(default_factory=list)
    fallback_chain: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)

# ══════════════════════════════════════════════════════════════════════════════
# Task and Attempt States
# ══════════════════════════════════════════════════════════════════════════════

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}")
    session_id: str
    title: str
    requirements: str
    status: Literal["pending", "running", "paused", "completed", "failed", "cancelled"] = "pending"
    context: TaskContext
    route_decision: Optional[RouteDecision] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:12]}")
    task_id: str
    attempt_id: str
    type: Literal["shell", "network", "dependency", "destructive", "git_commit", "git_push", "protected_file", "policy_override", "apply_changes"]
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "approved", "denied"] = "pending"
    created_at: float = Field(default_factory=time.time)
    decided_at: Optional[float] = None
    response_reason: Optional[str] = None

class VerificationRun(BaseModel):
    run_id: str = Field(default_factory=lambda: f"veri-{uuid.uuid4().hex[:12]}")
    task_id: str
    attempt_id: str
    commands_executed: List[str] = Field(default_factory=list)
    exit_status: int
    duration_sec: float
    stdout: str
    stderr: str
    changed_diagnostics: Optional[Dict[str, Any]] = None
    failed_tests: List[str] = Field(default_factory=list)
    failure_classification: Optional[Literal["environmental", "model_related", "requirement_related", "policy_related"]] = None
    timestamp: float = Field(default_factory=time.time)

class ExecutionAttempt(BaseModel):
    attempt_id: str = Field(default_factory=lambda: f"att-{uuid.uuid4().hex[:12]}")
    task_id: str
    attempt_number: int
    route_decision: RouteDecision
    worktree_path: str
    status: Literal["running", "success", "failed", "escalated"] = "running"
    patch: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    verification: Optional[VerificationRun] = None
    error_message: Optional[str] = None
    started_at: float = Field(default_factory=time.time)
    ended_at: Optional[float] = None

class EscalationDecision(BaseModel):
    escalation_id: str = Field(default_factory=lambda: f"escal-{uuid.uuid4().hex[:12]}")
    task_id: str
    previous_attempt_id: str
    previous_tier: str
    new_tier: str
    escalation_reason: str
    failure_classification: str
    timestamp: float = Field(default_factory=time.time)

# ══════════════════════════════════════════════════════════════════════════════
# Catalog descriptors & audit
# ══════════════════════════════════════════════════════════════════════════════

class ModelDescriptor(BaseModel):
    model_identifier: str
    display_name: str
    executor: Literal["Ollama", "Codex"]
    supported_reasoning_efforts: List[str] = Field(default_factory=list)
    supported_input_modalities: List[str] = Field(default_factory=list)
    is_available: bool = True
    discovery_timestamp: float = Field(default_factory=time.time)
    capabilities: List[str] = Field(default_factory=list) # e.g. ["generation", "coding", "vision"]

class WorkerDescriptor(BaseModel):
    worker_id: str
    host_name: str
    binding_address: str
    status: Literal["healthy", "unreachable", "degraded"] = "healthy"
    last_heartbeat: float = Field(default_factory=time.time)
    permitted_repository_roots: List[str] = Field(default_factory=list)
    capabilities: Dict[str, Any] = Field(default_factory=dict)

class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"audit-{uuid.uuid4().hex[:12]}")
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    origin: Literal["control_plane", "worker", "extension"]
    event_type: str
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
