import asyncio
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_APPROVAL_TIMEOUT_SECONDS = int(os.getenv("COGNITO_APPROVAL_TIMEOUT_SECONDS", "30"))

class ApprovalDecisionAudit(BaseModel):
    approval_id: str
    session_id: str
    action: str
    actor: str = "operator"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str  # "approved", "denied", "timed_out"
    reason: Optional[str] = None


class PendingApprovalRequest(BaseModel):
    approval_id: str
    session_id: str
    tool_name: str
    arguments: Dict[str, Any]
    command: Optional[str] = None
    reason: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timeout_seconds: int = DEFAULT_APPROVAL_TIMEOUT_SECONDS


class PendingApprovalState:
    def __init__(self, request: PendingApprovalRequest):
        self.request = request
        self.future: asyncio.Future[ApprovalDecisionAudit] = asyncio.get_running_loop().create_future()


class ApprovalManager:
    """
    Manages human-in-the-loop approval requests for sensitive actions.
    Pauses agent execution until explicit decision or timeout.
    Tracks structured audit log records designed for future SIEM integration (AUD-009).
    """

    def __init__(self, default_timeout_seconds: Optional[int] = None):
        self._pending: Dict[str, PendingApprovalState] = {}
        self._audit_log: List[ApprovalDecisionAudit] = []
        self._lock = asyncio.Lock()
        self.default_timeout_seconds = (
            default_timeout_seconds
            if default_timeout_seconds is not None
            else DEFAULT_APPROVAL_TIMEOUT_SECONDS
        )

    async def create_request(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: str,
        command: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        approval_id: Optional[str] = None,
    ) -> PendingApprovalRequest:
        """
        Registers a pending approval request in state without blocking execution.
        """
        appr_id = approval_id or f"appr-{uuid.uuid4().hex[:12]}"
        effective_timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds

        request = PendingApprovalRequest(
            approval_id=appr_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            command=command,
            reason=reason,
            timeout_seconds=effective_timeout,
        )

        state = PendingApprovalState(request)

        async with self._lock:
            self._pending[appr_id] = state

        logger.info(
            f"Approval registered [{appr_id}] for session {session_id} | "
            f"tool={tool_name} | command={command or 'N/A'} | timeout={effective_timeout}s"
        )

        return request

    async def wait_for_decision(self, approval_id: str) -> ApprovalDecisionAudit:
        """
        Awaits a decision on a previously created pending approval request, enforcing timeout and fallback denial.
        """
        async with self._lock:
            state = self._pending.get(approval_id)

        if not state:
            raise KeyError(f"Approval request '{approval_id}' not found in pending state.")

        effective_timeout = state.request.timeout_seconds
        session_id = state.request.session_id
        tool_name = state.request.tool_name
        arguments = state.request.arguments
        command = state.request.command

        try:
            decision = await asyncio.wait_for(
                asyncio.shield(state.future), timeout=float(effective_timeout)
            )
        except asyncio.TimeoutError:
            logger.warning(f"Approval request [{approval_id}] timed out after {effective_timeout}s. Denying by default.")
            decision = ApprovalDecisionAudit(
                approval_id=approval_id,
                session_id=session_id,
                action=command or f"{tool_name}:{arguments}",
                actor="system_timeout",
                status="timed_out",
                reason=f"No operator response within {effective_timeout} seconds timeout.",
            )
            if not state.future.done():
                state.future.set_result(decision)
        finally:
            async with self._lock:
                self._pending.pop(approval_id, None)

        async with self._lock:
            self._audit_log.append(decision)

        return decision

    async def request_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: str,
        command: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        approval_id: Optional[str] = None,
    ) -> ApprovalDecisionAudit:
        """
        Registers request and awaits decision in a single call.
        """
        req = await self.create_request(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            command=command,
            timeout_seconds=timeout_seconds,
            approval_id=approval_id,
        )
        return await self.wait_for_decision(req.approval_id)

    async def submit_decision(
        self,
        approval_id: str,
        approved: bool,
        actor: str = "operator",
        reason: Optional[str] = None,
    ) -> Optional[ApprovalDecisionAudit]:
        """
        Submits an operator decision ('approved' or 'denied') for a pending request.
        Resolves the paused agent future.
        """
        async with self._lock:
            state = self._pending.get(approval_id)

        if not state:
            logger.warning(f"No pending approval found for ID {approval_id}")
            return None

        status = "approved" if approved else "denied"
        decision = ApprovalDecisionAudit(
            approval_id=approval_id,
            session_id=state.request.session_id,
            action=state.request.command or f"{state.request.tool_name}:{state.request.arguments}",
            actor=actor,
            status=status,
            reason=reason or f"Manually {status} by {actor}",
        )

        if not state.future.done():
            state.future.set_result(decision)

        return decision

    async def list_pending(self, session_id: Optional[str] = None) -> List[PendingApprovalRequest]:
        """
        Lists active pending approval requests.
        """
        async with self._lock:
            requests = [s.request for s in self._pending.values()]
        if session_id:
            return [r for r in requests if r.session_id == session_id]
        return requests

    async def get_audit_logs(self, session_id: Optional[str] = None) -> List[ApprovalDecisionAudit]:
        """
        Retrieves recorded structured audit decision logs.
        """
        async with self._lock:
            logs = list(self._audit_log)
        if session_id:
            return [l for l in logs if l.session_id == session_id]
        return logs


# Default global instance
approval_manager = ApprovalManager()
