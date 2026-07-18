import time
from typing import List, Optional
from sqlalchemy import select, update
from app.core.database import async_session_factory
from app.models.db import DBTask, DBExecutionAttempt, DBApprovalRequest, DBVerificationRun
from app.models.domain import Task, ExecutionAttempt, ApprovalRequest, VerificationRun, TaskContext, RouteDecision

class TaskStore:
    def __init__(self):
        # Fallback dictionary for testing environments if DB session fails
        self._fallback_tasks = {}
        self._fallback_attempts = {}
        self._fallback_approvals = {}

    async def create_task(self, task: Task) -> Task:
        try:
            async with async_session_factory() as session:
                db_task = DBTask(
                    task_id=task.task_id,
                    session_id=task.session_id,
                    title=task.title,
                    requirements=task.requirements,
                    status=task.status,
                    context=task.context.model_dump(),
                    route_decision=task.route_decision.model_dump() if task.route_decision else None,
                    created_at=task.created_at,
                    updated_at=task.updated_at
                )
                session.add(db_task)
                await session.commit()
                return task
        except Exception:
            self._fallback_tasks[task.task_id] = task
            return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        try:
            async with async_session_factory() as session:
                res = await session.execute(select(DBTask).where(DBTask.task_id == task_id))
                row = res.scalar_one_or_none()
                if row:
                    return Task(
                        task_id=row.task_id,
                        session_id=row.session_id,
                        title=row.title,
                        requirements=row.requirements,
                        status=row.status,
                        context=TaskContext.model_validate(row.context),
                        route_decision=RouteDecision.model_validate(row.route_decision) if row.route_decision else None,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
        except Exception:
            pass
        return self._fallback_tasks.get(task_id)

    async def list_tasks(self, session_id: Optional[str] = None) -> List[Task]:
        try:
            async with async_session_factory() as session:
                stmt = select(DBTask)
                if session_id:
                    stmt = stmt.where(DBTask.session_id == session_id)
                res = await session.execute(stmt)
                tasks = []
                for row in res.scalars().all():
                    tasks.append(Task(
                        task_id=row.task_id,
                        session_id=row.session_id,
                        title=row.title,
                        requirements=row.requirements,
                        status=row.status,
                        context=TaskContext.model_validate(row.context),
                        route_decision=RouteDecision.model_validate(row.route_decision) if row.route_decision else None,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    ))
                return tasks
        except Exception:
            all_fallback = list(self._fallback_tasks.values())
            if session_id:
                return [t for t in all_fallback if t.session_id == session_id]
            return all_fallback

    async def update_task_status(self, task_id: str, status: str) -> Optional[Task]:
        task = await self.get_task(task_id)
        if task:
            task.status = status
            task.updated_at = time.time()
            try:
                async with async_session_factory() as session:
                    await session.execute(
                        update(DBTask)
                        .where(DBTask.task_id == task_id)
                        .values(status=status, updated_at=task.updated_at)
                    )
                    await session.commit()
            except Exception:
                self._fallback_tasks[task_id] = task
        return task

    async def create_attempt(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        try:
            async with async_session_factory() as session:
                db_att = DBExecutionAttempt(
                    attempt_id=attempt.attempt_id,
                    task_id=attempt.task_id,
                    attempt_number=attempt.attempt_number,
                    route_decision=attempt.route_decision.model_dump(),
                    worktree_path=attempt.worktree_path,
                    status=attempt.status,
                    patch=attempt.patch,
                    changed_files=attempt.changed_files,
                    verification=attempt.verification.model_dump() if attempt.verification else None,
                    error_message=attempt.error_message,
                    started_at=attempt.started_at,
                    ended_at=attempt.ended_at
                )
                session.add(db_att)
                await session.commit()
        except Exception:
            if attempt.task_id not in self._fallback_attempts:
                self._fallback_attempts[attempt.task_id] = []
            self._fallback_attempts[attempt.task_id].append(attempt)
        return attempt

    async def get_attempts(self, task_id: str) -> List[ExecutionAttempt]:
        try:
            async with async_session_factory() as session:
                res = await session.execute(
                    select(DBExecutionAttempt).where(DBExecutionAttempt.task_id == task_id)
                )
                attempts = []
                for row in res.scalars().all():
                    attempts.append(ExecutionAttempt(
                        attempt_id=row.attempt_id,
                        task_id=row.task_id,
                        attempt_number=row.attempt_number,
                        route_decision=RouteDecision.model_validate(row.route_decision),
                        worktree_path=row.worktree_path,
                        status=row.status,
                        patch=row.patch,
                        changed_files=row.changed_files,
                        verification=VerificationRun.model_validate(row.verification) if row.verification else None,
                        error_message=row.error_message,
                        started_at=row.started_at,
                        ended_at=row.ended_at
                    ))
                return attempts
        except Exception:
            pass
        return self._fallback_attempts.get(task_id, [])

    async def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        try:
            async with async_session_factory() as session:
                db_appr = DBApprovalRequest(
                    approval_id=approval.approval_id,
                    task_id=approval.task_id,
                    attempt_id=approval.attempt_id,
                    type=approval.type,
                    description=approval.description,
                    details=approval.details,
                    status=approval.status,
                    created_at=approval.created_at,
                    decided_at=approval.decided_at,
                    response_reason=approval.response_reason
                )
                session.add(db_appr)
                await session.commit()
        except Exception:
            if approval.task_id not in self._fallback_approvals:
                self._fallback_approvals[approval.task_id] = []
            self._fallback_approvals[approval.task_id].append(approval)
        return approval

    async def get_approvals(self, task_id: str) -> List[ApprovalRequest]:
        try:
            async with async_session_factory() as session:
                res = await session.execute(
                    select(DBApprovalRequest).where(DBApprovalRequest.task_id == task_id)
                )
                approvals = []
                for row in res.scalars().all():
                    approvals.append(ApprovalRequest(
                        approval_id=row.approval_id,
                        task_id=row.task_id,
                        attempt_id=row.attempt_id,
                        type=row.type,
                        description=row.description,
                        details=row.details,
                        status=row.status,
                        created_at=row.created_at,
                        decided_at=row.decided_at,
                        response_reason=row.response_reason
                    ))
                return approvals
        except Exception:
            pass
        return self._fallback_approvals.get(task_id, [])

    async def update_approval(self, approval_id: str, status: str, reason: Optional[str] = None) -> Optional[ApprovalRequest]:
        # Update fallbacks first
        for task_id, approvals in self._fallback_approvals.items():
            for appr in approvals:
                if appr.approval_id == approval_id:
                    appr.status = status
                    appr.decided_at = time.time()
                    appr.response_reason = reason
                    return appr

        try:
            async with async_session_factory() as session:
                res = await session.execute(
                    select(DBApprovalRequest).where(DBApprovalRequest.approval_id == approval_id)
                )
                row = res.scalar_one_or_none()
                if row:
                    row.status = status
                    row.decided_at = time.time()
                    row.response_reason = reason
                    await session.commit()
                    return ApprovalRequest(
                        approval_id=row.approval_id,
                        task_id=row.task_id,
                        attempt_id=row.attempt_id,
                        type=row.type,
                        description=row.description,
                        details=row.details,
                        status=row.status,
                        created_at=row.created_at,
                        decided_at=row.decided_at,
                        response_reason=row.response_reason
                    )
        except Exception:
            pass
        return None

task_store = TaskStore()
