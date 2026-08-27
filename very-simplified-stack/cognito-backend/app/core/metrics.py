import threading
import logging
from typing import Dict, Any, Optional, Tuple, FrozenSet

logger = logging.getLogger("cognito.backend.metrics")


class CognitoMetrics:
    """
    In-memory Prometheus metrics exporter for Cognito Backend.
    Supports Counters, Gauges, and Histograms (sum/count) with custom label sets.
    Generates plain-text Prometheus Exposition format (v0.0.4) directly without external SDK dependencies.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Metadata storage: metric_name -> {"help": str, "type": str}
        self._metadata: Dict[str, Dict[str, str]] = {}

        # Metric values: (metric_name, frozen_labels_tuple) -> float or dict
        self._counters: Dict[Tuple[str, FrozenSet[Tuple[str, str]]], float] = {}
        self._gauges: Dict[Tuple[str, FrozenSet[Tuple[str, str]]], float] = {}
        self._histograms: Dict[Tuple[str, FrozenSet[Tuple[str, str]]], Dict[str, float]] = {}

        # Register default backend metrics metadata
        self._register_default_metadata()

    def _register_default_metadata(self):
        # Operational Latency
        self.register_metric(
            "cognito_operation_duration_seconds",
            "Duration of backend operations in seconds",
            "histogram"
        )
        # Tool Failures
        self.register_metric(
            "cognito_tool_failures_total",
            "Total failures encountered during tool executions",
            "counter"
        )
        # Retries
        self.register_metric(
            "cognito_retries_total",
            "Total retry attempts made during backend operations",
            "counter"
        )
        # Token Consumption
        self.register_metric(
            "cognito_tokens_total",
            "Total AI tokens consumed per user and model",
            "counter"
        )
        # Cost Consumption
        self.register_metric(
            "cognito_cost_dollars_total",
            "Total estimated AI cost in USD per user and model",
            "counter"
        )

        # Legacy / simple metrics
        self.register_metric("cognito_tasks_total", "Total tasks created", "counter")
        self.register_metric("cognito_tasks_active", "Number of currently active tasks", "gauge")
        self.register_metric("cognito_route_decisions_total", "Total route decisions made", "counter")
        self.register_metric("cognito_route_overrides_total", "Total route overrides made by users", "counter")
        self.register_metric("cognito_attempts_total", "Total execution attempts made", "counter")
        self.register_metric("cognito_task_duration_seconds", "Duration of tasks in seconds", "histogram")
        self.register_metric("cognito_codex_turn_duration_seconds", "Duration of Codex execution turns in seconds", "histogram")
        self.register_metric("cognito_ollama_classifier_duration_seconds", "Ollama task classification duration", "histogram")
        self.register_metric("cognito_verification_runs_total", "Total verification runs executed", "counter")
        self.register_metric("cognito_verification_failures_total", "Total verification failures observed", "counter")
        self.register_metric("cognito_escalations_total", "Total automatic task escalations", "counter")
        self.register_metric("cognito_approvals_total", "Total approvals requested", "counter")
        self.register_metric("cognito_worker_heartbeat_age_seconds", "Age of last worker heartbeat", "gauge")
        self.register_metric("cognito_worker_failures_total", "Total worker connectivity/execution failures", "counter")
        self.register_metric("cognito_worktree_cleanup_failures_total", "Total worktree cleanup failures", "counter")
        self.register_metric("cognito_outbox_pending_events", "Pending transactional outbox events", "gauge")

    def register_metric(self, name: str, help_text: str, metric_type: str):
        with self._lock:
            self._metadata[name] = {"help": help_text, "type": metric_type}

    def _labels_key(self, labels: Optional[Dict[str, str]]) -> FrozenSet[Tuple[str, str]]:
        if not labels:
            return frozenset()
        # Filter out empty label values if needed, or keep non-null string values
        clean_labels = {str(k): str(v) for k, v in labels.items() if v is not None and str(v) != ""}
        return frozenset(sorted(clean_labels.items()))

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None, help_text: str = ""):
        if help_text and name not in self._metadata:
            self.register_metric(name, help_text, "counter")
        elif name not in self._metadata:
            self.register_metric(name, f"Counter metric {name}", "counter")

        key = (name, self._labels_key(labels))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None, help_text: str = ""):
        if help_text and name not in self._metadata:
            self.register_metric(name, help_text, "gauge")
        elif name not in self._metadata:
            self.register_metric(name, f"Gauge metric {name}", "gauge")

        key = (name, self._labels_key(labels))
        with self._lock:
            self._gauges[key] = float(value)

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None, help_text: str = ""):
        if help_text and name not in self._metadata:
            self.register_metric(name, help_text, "histogram")
        elif name not in self._metadata:
            self.register_metric(name, f"Histogram metric {name}", "histogram")

        key = (name, self._labels_key(labels))
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = {"sum": 0.0, "count": 0.0}
            self._histograms[key]["sum"] += float(value)
            self._histograms[key]["count"] += 1.0

    # Operational helper methods for AUD-024 requirements
    def record_operation_duration(self, operation: str, duration_seconds: float, trace_id: str = ""):
        labels = {"operation": operation}
        if trace_id:
            labels["trace_id"] = trace_id
        self.observe_histogram("cognito_operation_duration_seconds", duration_seconds, labels=labels)

    def record_tool_failure(self, tool_name: str, trace_id: str = ""):
        labels = {"tool_name": tool_name}
        if trace_id:
            labels["trace_id"] = trace_id
        self.inc_counter("cognito_tool_failures_total", 1.0, labels=labels)

    def record_retry(self, operation: str, trace_id: str = ""):
        labels = {"operation": operation}
        if trace_id:
            labels["trace_id"] = trace_id
        self.inc_counter("cognito_retries_total", 1.0, labels=labels)

    def record_tokens(self, user_id: str, model: str, token_type: str, count: float, trace_id: str = ""):
        labels = {"user_id": user_id or "anonymous", "model": model or "unknown", "token_type": token_type}
        if trace_id:
            labels["trace_id"] = trace_id
        self.inc_counter("cognito_tokens_total", float(count), labels=labels)

    def record_cost(self, user_id: str, model: str, amount_dollars: float, trace_id: str = ""):
        labels = {"user_id": user_id or "anonymous", "model": model or "unknown"}
        if trace_id:
            labels["trace_id"] = trace_id
        self.inc_counter("cognito_cost_dollars_total", float(amount_dollars), labels=labels)

    # Legacy method compatibility
    def increment(self, name: str, value: float = 1.0):
        name = name if name.startswith("cognito_") else f"cognito_{name}"
        self.inc_counter(name, value)

    def set_value(self, name: str, value: float):
        name = name if name.startswith("cognito_") else f"cognito_{name}"
        self.set_gauge(name, value)

    def record_time(self, name: str, value: float):
        name = name if name.startswith("cognito_") else f"cognito_{name}"
        self.observe_histogram(name, value)

    @property
    def in_memory_metrics(self) -> Dict[str, float]:
        """
        Backward compatibility property returning simple metric name -> value dict.
        """
        res: Dict[str, float] = {}
        with self._lock:
            for (name, labels), val in self._counters.items():
                res[name] = val
            for (name, labels), val in self._gauges.items():
                res[name] = val
            for (name, labels), hist in self._histograms.items():
                res[f"{name}_sum"] = hist["sum"]
                res[f"{name}_count"] = hist["count"]
        return res

    def _format_labels(self, labels_tuple: FrozenSet[Tuple[str, str]]) -> str:
        if not labels_tuple:
            return ""
        formatted_pairs = []
        for k, v in sorted(labels_tuple):
            escaped_v = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            formatted_pairs.append(f'{k}="{escaped_v}"')
        return "{" + ",".join(formatted_pairs) + "}"

    def generate_prometheus_text(self) -> str:
        """
        Exports all registered and recorded metrics into standard Prometheus Exposition Text Format (v0.0.4).
        """
        lines = []

        with self._lock:
            # Group recorded entries by metric name
            metrics_by_name: Dict[str, Dict[str, Any]] = {}

            # Gather metadata
            for name, meta in self._metadata.items():
                metrics_by_name[name] = {
                    "help": meta["help"],
                    "type": meta["type"],
                    "counters": [],
                    "gauges": [],
                    "histograms": [],
                }

            # Collect counter samples
            for (name, labels), val in self._counters.items():
                if name not in metrics_by_name:
                    metrics_by_name[name] = {"help": f"Metric {name}", "type": "counter", "counters": [], "gauges": [], "histograms": []}
                metrics_by_name[name]["counters"].append((labels, val))

            # Collect gauge samples
            for (name, labels), val in self._gauges.items():
                if name not in metrics_by_name:
                    metrics_by_name[name] = {"help": f"Metric {name}", "type": "gauge", "counters": [], "gauges": [], "histograms": []}
                metrics_by_name[name]["gauges"].append((labels, val))

            # Collect histogram samples
            for (name, labels), hist in self._histograms.items():
                if name not in metrics_by_name:
                    metrics_by_name[name] = {"help": f"Metric {name}", "type": "histogram", "counters": [], "gauges": [], "histograms": []}
                metrics_by_name[name]["histograms"].append((labels, hist))

            # Render metrics
            for name, data in sorted(metrics_by_name.items()):
                has_samples = bool(data["counters"] or data["gauges"] or data["histograms"])
                # Always render metric header if registered or has samples
                lines.append(f"# HELP {name} {data['help']}")
                lines.append(f"# TYPE {name} {data['type']}")

                metric_type = data["type"]

                if metric_type == "counter":
                    if data["counters"]:
                        for labels, val in sorted(data["counters"], key=lambda x: sorted(x[0])):
                            lbl_str = self._format_labels(labels)
                            lines.append(f"{name}{lbl_str} {val}")
                    elif not has_samples:
                        lines.append(f"{name} 0")

                elif metric_type == "gauge":
                    if data["gauges"]:
                        for labels, val in sorted(data["gauges"], key=lambda x: sorted(x[0])):
                            lbl_str = self._format_labels(labels)
                            lines.append(f"{name}{lbl_str} {val}")
                    elif not has_samples:
                        lines.append(f"{name} 0")

                elif metric_type == "histogram":
                    if data["histograms"]:
                        for labels, hist in sorted(data["histograms"], key=lambda x: sorted(x[0])):
                            lbl_str = self._format_labels(labels)
                            lines.append(f"{name}_sum{lbl_str} {hist['sum']}")
                            lines.append(f"{name}_count{lbl_str} {hist['count']}")
                    elif not has_samples:
                        lines.append(f"{name}_sum 0")
                        lines.append(f"{name}_count 0")

                lines.append("")  # Empty line separator

        return "\n".join(lines) + "\n"


metrics = CognitoMetrics()
