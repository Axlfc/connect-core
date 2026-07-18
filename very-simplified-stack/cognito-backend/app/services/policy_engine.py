import os
import tomllib
import re
import logging
from typing import Dict, Any, Optional, List
from app.models.domain import TaskContext, RouteDecision, ExecutionPolicy, SandboxPolicy, NetworkPolicy, ApprovalPolicy
from app.services.ollama_classifier import ClassificationResponse, ClassificationResponse

logger = logging.getLogger("cognito.services.policy_engine")

class PolicyEngine:
    def __init__(self, policy_path: Optional[str] = None):
        self.policy_path = policy_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "core", "policies", "default_policy.toml"
        )
        self.policy_data = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        try:
            with open(self.policy_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            logger.warning(f"Failed to load policy TOML from {self.policy_path}, using defaults: {e}")
            # Minimal hardcoded fallback
            return {
                "metadata": {"version": "1.0.0"},
                "overrides": {
                    "sol_force_patterns": ["auth", "login", "permission", "secret", "migration", "ci/cd", "race condition"],
                    "luna_prefer_patterns": ["rename", "formatting", "lint", "boilerplate"],
                    "ollama_prefer_patterns": ["explain", "what is", "how does", "summarize"]
                }
            }

    def validate_policy(self) -> bool:
        """Validate loaded policy schema."""
        try:
            overrides = self.policy_data.get("overrides", {})
            required_keys = ["sol_force_patterns", "luna_prefer_patterns", "ollama_prefer_patterns"]
            for k in required_keys:
                if k not in overrides or not isinstance(overrides[k], list):
                    return False
            return True
        except Exception:
            return False

    def evaluate(self, context: TaskContext, classification: ClassificationResponse) -> RouteDecision:
        user_task = context.user_task.lower()
        overrides = self.policy_data.get("overrides", {})

        executor = "Codex"
        logical_tier = classification.recommended_logical_tier
        mode = "act"
        risk = classification.risk
        confidence = classification.confidence
        reasons = list(classification.reasons)
        constraints = []
        verification = ["lint", "typecheck"]

        # Sandbox, network and approval policies
        sandbox = SandboxPolicy(allowed_writable_roots=[context.editor.workspace_folder])
        network = NetworkPolicy(allow_all=classification.expected_network_requirement)
        approval = ApprovalPolicy(
            require_approval_for_shell=True,
            require_approval_for_write=classification.risk == "high",
            require_approval_for_destructive=True
        )

        # 1. Check for Ollama-prefer pattern overrides (Read-only / Explanation)
        for pattern in overrides.get("ollama_prefer_patterns", []):
            if pattern in user_task or any(pattern in s.lower() for s in context.task_history_indicators):
                executor = "Ollama"
                logical_tier = "local"
                mode = "read"
                risk = "low"
                sandbox.read_only = True
                reasons.append(f"Forced read-only Ollama route due to pattern match: '{pattern}'")
                break

        # If not read-only, check for high-risk / Sol overrides
        if executor != "Ollama":
            force_sol = False
            for pattern in overrides.get("sol_force_patterns", []):
                if pattern in user_task or any(pattern in p.lower() for p in context.sensitive_path_indicators):
                    force_sol = True
                    reasons.append(f"Forced plan-first Sol route due to high-risk pattern match: '{pattern}'")
                    break

            if force_sol:
                logical_tier = "sol"
                mode = "plan"
                risk = "high"
                approval.require_approval_for_write = True
                approval.require_approval_for_shell = True
                constraints.append("Read-only planning session required before execution.")
                verification.extend(["tests", "integration_tests"])
            else:
                # Check for Luna overrides if risk is low/medium
                for pattern in overrides.get("luna_prefer_patterns", []):
                    if pattern in user_task:
                        logical_tier = "luna"
                        mode = "act"
                        risk = "low"
                        reasons.append(f"Preferred mechanical Luna route due to pattern match: '{pattern}'")
                        break

        # Map logical tier to mock or resolved model identifier
        model_id = "qwen3.5:9b"  # Default
        if executor == "Ollama":
            model_id = "qwen3.5:9b"
        else:
            if logical_tier == "luna":
                model_id = "codex.economy"
            elif logical_tier == "terra":
                model_id = "codex.balanced"
            elif logical_tier == "sol":
                model_id = "codex.max"

        policy = ExecutionPolicy(sandbox=sandbox, network=network, approval=approval)

        return RouteDecision(
            executor=executor,
            logical_tier=logical_tier,
            resolved_model_identifier=model_id,
            mode=mode,
            risk=risk,
            confidence=confidence,
            execution_policy=policy,
            reasons=reasons,
            execution_constraints=constraints,
            verification_requirements=verification,
            fallback_chain=["terra", "sol"] if logical_tier == "luna" else ["sol"]
        )

policy_engine = PolicyEngine()
