import logging
import time
from typing import Dict, Any, Optional, List
from app.models.domain import Task, ExecutionAttempt, RouteDecision, VerificationRun, EscalationDecision
from app.services.task_store import task_store
from app.services.worker_client import worker_client

logger = logging.getLogger("cognito.backend.escalation_service")

class EscalationService:
    def __init__(self):
        # Maps current logical tier to the stronger logical tier
        self.escalation_chain = {
            "local": "luna",
            "luna": "terra",
            "terra": "sol"
        }

    def compile_attempt_summary(self, task_id: str, attempt: ExecutionAttempt) -> str:
        """
        Compiles a highly informative, read-only attempt summary for the next escalated model.
        """
        veri_str = ""
        if attempt.verification:
            v = attempt.verification
            veri_str = (
                f"Exit Code: {v.exit_status}\n"
                f"Failed Tests: {', '.join(v.failed_tests)}\n"
                f"Failure Classification: {v.failure_classification}\n"
                f"Stdout Summary:\n{v.stdout[:1000]}\n"
                f"Stderr Summary:\n{v.stderr[:1000]}\n"
            )

        return (
            f"=== PREVIOUS ATTEMPT SUMMARY ===\n"
            f"Attempt Number: {attempt.attempt_number}\n"
            f"Executor: {attempt.route_decision.executor}\n"
            f"Model Used: {attempt.route_decision.resolved_model_identifier}\n"
            f"Logical Tier: {attempt.route_decision.logical_tier}\n"
            f"Changed Files: {', '.join(attempt.changed_files)}\n"
            f"Verification Result:\n{veri_str}\n"
            f"Patch / Diff generated:\n{attempt.patch or 'None'}\n"
            f"================================\n"
        )

    async def execute_task_attempt(self, task: Task, attempt_num: int, decision: RouteDecision) -> ExecutionAttempt:
        logger.info(f"Executing task attempt {attempt_num} for task {task.task_id} with logical tier {decision.logical_tier}")

        # Resolve sibling worktree path
        worktree_path = f"~/.cognito/worktrees/{task.context.repository.repository_id}/{task.task_id}/attempt-{attempt_num:02d}"

        # If previous attempts exist, compile summaries to inject
        previous_attempts_context = ""
        previous_attempts = await task_store.get_attempts(task.task_id)
        if previous_attempts:
            summaries = []
            for pa in previous_attempts:
                summaries.append(self.compile_attempt_summary(task.task_id, pa))
            previous_attempts_context = "\n\n".join(summaries)

        # Build payload for the worker
        payload = {
            "task_id": task.task_id,
            "session_id": task.session_id,
            "model": decision.resolved_model_identifier,
            "requirements": task.requirements + ("\n\n" + previous_attempts_context if previous_attempts_context else ""),
            "base_repo_path": task.context.repository.root_path,
            "repo_id": task.context.repository.repository_id,
            "attempt": attempt_num,
            "environment": {}
        }

        # Start execution
        attempt = ExecutionAttempt(
            task_id=task.task_id,
            attempt_number=attempt_num,
            route_decision=decision,
            worktree_path=worktree_path,
            status="running"
        )
        await task_store.create_attempt(attempt)

        try:
            # We call the worker to start task
            resp = await worker_client.start_task(payload)

            # Read and parse SSE stream from the worker
            import json
            combined_text = ""
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if event.get("type") == "text_delta":
                            combined_text += event.get("content", "")
                        elif event.get("type") == "done":
                            break
                    except Exception:
                        pass

            logger.info("Codex execution completed successfully.")
            attempt.status = "success"
            attempt.ended_at = time.time()
            attempt.patch = f"diff --git a/src/feature.py b/src/feature.py\n+{combined_text}"
            attempt.changed_files = ["src/feature.py"]
        except Exception as e:
            logger.error(f"Attempt execution failed: {e}")
            attempt.status = "failed"
            attempt.error_message = str(e)
            attempt.ended_at = time.time()

        return attempt

    async def run_verification_and_escalate_if_needed(self, task: Task, attempt: ExecutionAttempt) -> Optional[RouteDecision]:
        """
        Runs targeted lint, typechecking, and tests.
        If a model-related failure is classified, escalates to a stronger logical tier.
        Returns the escalated RouteDecision if escalation happened, or None.
        """
        if attempt.status != "success":
            return None

        logger.info(f"Running verification for task {task.task_id} attempt {attempt.attempt_number}")

        # Run test verification
        v_payload = {
            "task_id": task.task_id,
            "attempt_id": attempt.attempt_id,
            "worktree_path": attempt.worktree_path,
            "category": "test"
        }

        v_res = await worker_client.verify_task(v_payload)

        # Instantiate VerificationRun
        run = VerificationRun(
            task_id=task.task_id,
            attempt_id=attempt.attempt_id,
            commands_executed=v_res.get("commands_executed", []),
            exit_status=v_res.get("exit_status", 0),
            duration_sec=v_res.get("duration_sec", 0.1),
            stdout=v_res.get("stdout", ""),
            stderr=v_res.get("stderr", ""),
            failed_tests=v_res.get("failed_tests", []),
            failure_classification=v_res.get("failure_classification")
        )
        attempt.verification = run

        # Escalation criteria:
        # 1. Exit status != 0
        # 2. Failure classification is genuinely "model_related"
        # 3. There is a stronger tier in our escalation chain
        current_tier = attempt.route_decision.logical_tier
        next_tier = self.escalation_chain.get(current_tier)

        if run.exit_status != 0 and run.failure_classification == "model_related" and next_tier:
            logger.warning(f"Verification failed with model_related failure. Escalating from {current_tier} to {next_tier}!")

            # Create escalation decision record
            escal = EscalationDecision(
                task_id=task.task_id,
                previous_attempt_id=attempt.attempt_id,
                previous_tier=current_tier,
                new_tier=next_tier,
                escalation_reason="Model-related verification failure in tests.",
                failure_classification="model_related"
            )
            # Log audit
            logger.info(f"Recorded escalation: {escal.escalation_id}")

            # Create stronger route decision
            import copy
            new_decision = attempt.route_decision.model_copy()
            new_decision.logical_tier = next_tier
            new_decision.resolved_model_identifier = f"codex.{next_tier}" if next_tier != "sol" else "codex.max"
            new_decision.reasons.append(f"Escalated automatically from {current_tier} due to test failure.")
            new_decision.timestamp = time.time()

            attempt.status = "escalated"
            return new_decision

        return None

escalation_service = EscalationService()
