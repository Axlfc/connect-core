import logging
from typing import Dict, Any

logger = logging.getLogger("cognito.backend.metrics")

# Optional prometheus client support
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary
    prometheus_available = True
except ImportError:
    prometheus_available = False

class CognitoMetrics:
    def __init__(self):
        self.in_memory_metrics: Dict[str, float] = {}

        if prometheus_available:
            self.tasks_total = Counter("cognito_tasks_total", "Total tasks created")
            self.tasks_active = Gauge("cognito_tasks_active", "Number of currently active tasks")
            self.route_decisions = Counter("cognito_route_decisions_total", "Total route decisions made")
            self.route_overrides = Counter("cognito_route_overrides_total", "Total route overrides made by users")
            self.attempts_total = Counter("cognito_attempts_total", "Total execution attempts made")
            self.task_duration = Histogram("cognito_task_duration_seconds", "Duration of tasks in seconds")
            self.codex_turn_duration = Histogram("cognito_codex_turn_duration_seconds", "Duration of Codex execution turns in seconds")
            self.ollama_classifier_duration = Histogram("cognito_ollama_classifier_duration_seconds", "Ollama task classification duration")
            self.verification_runs = Counter("cognito_verification_runs_total", "Total verification runs executed")
            self.verification_failures = Counter("cognito_verification_failures_total", "Total verification failures observed")
            self.escalations_total = Counter("cognito_escalations_total", "Total automatic task escalations")
            self.approvals_total = Counter("cognito_approvals_total", "Total approvals requested")
            self.worker_heartbeat_age = Gauge("cognito_worker_heartbeat_age_seconds", "Age of last worker heartbeat")
            self.worker_failures = Counter("cognito_worker_failures_total", "Total worker connectivity/execution failures")
            self.cleanup_failures = Counter("cognito_worktree_cleanup_failures_total", "Total worktree cleanup failures")
            self.outbox_pending = Gauge("cognito_outbox_pending_events", "Pending transactional outbox events")
        else:
            logger.info("Prometheus client is not installed. Using in-memory fallback metrics.")

    def increment(self, name: str, value: float = 1.0):
        if prometheus_available:
            metric = getattr(self, name.replace("cognito_", ""), None)
            if metric and hasattr(metric, "inc"):
                metric.inc(value)
                return
        self.in_memory_metrics[name] = self.in_memory_metrics.get(name, 0.0) + value

    def set_value(self, name: str, value: float):
        if prometheus_available:
            metric = getattr(self, name.replace("cognito_", ""), None)
            if metric and hasattr(metric, "set"):
                metric.set(value)
                return
        self.in_memory_metrics[name] = value

    def record_time(self, name: str, value: float):
        if prometheus_available:
            metric = getattr(self, name.replace("cognito_", ""), None)
            if metric and hasattr(metric, "observe"):
                metric.observe(value)
                return
        self.in_memory_metrics[name] = value

metrics = CognitoMetrics()
