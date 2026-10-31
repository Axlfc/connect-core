"""
Jules Engine: Motor de Desarrollo Desatendido de Jules para Cognito Stack.
Ejecuta el ciclo de vida autónomo:
1. Registra la sesión y el mensaje inicial del usuario (userMessaged).
2. Genera el plan estructurado (planGenerated).
3. Ejecuta pasos usando agent_loop con herramientas (read, write, apply_unified_patch, bash).
4. Emite actualizaciones de progreso y artefactos (progressUpdated, artifacts, bashOutput, agentMessaged).
5. Captura los cambios reales en git (changeSet con unidiffPatch, baseCommitId y suggestedCommitMessage).
6. Completa la sesión (sessionCompleted) o maneja fallos resilientes.
"""

import os
import re
import json
import time
import uuid
import logging
import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.db import DBJulesSession, DBJulesActivity, DBSource
from app.core.session_manager import SessionManager
from app.core.resource_loader import ResourceLoader
from app.core.project_trust import ProjectTrustStore
from app.core.extensions.registry import extension_registry
from app.services.backend_router import backend_router
from app.services.semantic_orchestrator import semantic_orchestrator
from app.core.steering import steering_manager
from app.core.tools.base import ToolContext
from app.core.agent_loop import agent_loop
from app.core.events import (
    TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent
)

logger = logging.getLogger("cognito.jules.engine")

def now_iso() -> str:
    """Returns ISO 8601 UTC timestamp with high precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def resolve_workspace_for_source(source_str: Optional[str]) -> str:
    """
    Resolves the local workspace directory for a given Jules source identifier.
    Falls back to ALLOWED_REPOSITORY_ROOTS or current working directory.
    """
    allowed_roots = os.getenv("ALLOWED_REPOSITORY_ROOTS", "").split(",")
    valid_roots = [r.strip() for r in allowed_roots if r.strip() and os.path.isdir(r.strip())]

    if not source_str:
        return valid_roots[0] if valid_roots else os.getcwd()

    clean_source = source_str.replace("sources/", "")
    # clean_source might look like 'github/owner/repo' or 'owner/repo'
    parts = clean_source.split("/")
    repo_name = parts[-1] if parts else ""

    # Check if any valid root contains or matches repo_name
    for root in valid_roots:
        candidate = Path(root) / repo_name
        if candidate.is_dir():
            return str(candidate.resolve())
        if Path(root).name == repo_name:
            return str(Path(root).resolve())

    # Check relative to cwd
    cwd_path = Path(os.getcwd())
    if (cwd_path / repo_name).is_dir():
        return str((cwd_path / repo_name).resolve())
    if cwd_path.name == repo_name:
        return str(cwd_path.resolve())

    return valid_roots[0] if valid_roots else str(cwd_path.resolve())

def get_git_diff_and_base_commit(cwd: str) -> tuple[Optional[str], Optional[str]]:
    """
    Calculates git diff in workspace and detects the current base commit ID.
    Returns (unidiff_patch, base_commit_id).
    """
    try:
        # Check base commit
        commit_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        base_commit = commit_res.stdout.strip() if commit_res.returncode == 0 else "0000000000000000"

        # Check diff
        diff_res = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15
        )
        diff_text = diff_res.stdout
        if not diff_text:
            # Check untracked or staged diff
            diff_staged = subprocess.run(
                ["git", "diff", "--staged"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            diff_text = diff_staged.stdout

        return (diff_text if diff_text.strip() else None, base_commit)
    except Exception as e:
        logger.warning(f"Error obtaining git diff in {cwd}: {e}")
        return (None, None)

class JulesUnattendedEngine:
    """
    Orchestrates unattended coding tasks and runs the autonomous agent lifecycle.
    """

    async def execute_session_async(self, session_id: str, owner: str, prompt: str, source: Optional[str], title: Optional[str]):
        """
        Background worker that drives the unattended session execution.
        """
        logger.info(f"🚀 Starting Jules unattended session: {session_id} for owner: {owner}")
        workspace_cwd = resolve_workspace_for_source(source)
        logger.info(f"📂 Workspace mapped to: {workspace_cwd}")

        # 1. Update session state to RUNNING
        async with async_session_factory() as db:
            sess_res = await db.execute(select(DBJulesSession).where(DBJulesSession.session_id == session_id))
            db_session = sess_res.scalars().first()
            if db_session:
                payload = dict(db_session.payload)
                payload["state"] = "RUNNING"
                payload["updateTime"] = now_iso()
                db_session.payload = payload
                db_session.state = "RUNNING"
                db_session.update_time = payload["updateTime"]
                await db.commit()

        # Helper to append an activity to DBJulesActivity
        seq_counter = 0

        async def record_activity(activity_dict: Dict[str, Any], originator: str):
            nonlocal seq_counter
            seq_counter += 1
            act_id = activity_dict.get("id") or f"act-{session_id}-{seq_counter}"
            act_create_time = activity_dict.get("createTime") or now_iso()
            activity_dict["name"] = f"sessions/{session_id}/activities/{act_id}"
            activity_dict["id"] = act_id
            activity_dict["createTime"] = act_create_time
            activity_dict["originator"] = originator

            async with async_session_factory() as db:
                db_act = DBJulesActivity(
                    session_id=session_id,
                    activity_id=act_id,
                    seq=seq_counter,
                    payload=activity_dict,
                    originator=originator,
                    create_time=act_create_time
                )
                db.add(db_act)
                await db.commit()
            return activity_dict

        # 2. Record initial userMessaged activity
        await record_activity({
            "id": f"msg-user-{uuid.uuid4().hex[:12]}",
            "userMessaged": {
                "userMessage": prompt
            }
        }, originator="user")

        # 3. Formulate and record planGenerated
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        plan_activity = {
            "id": f"act-plan-{uuid.uuid4().hex[:8]}",
            "planGenerated": {
                "plan": {
                    "id": plan_id,
                    "createTime": now_iso(),
                    "steps": [
                        {
                            "id": "step-1",
                            "index": 1,
                            "title": "Analyze Task & Inspect Workspace",
                            "description": f"Examine codebase and project structure for task: {prompt[:120]}"
                        },
                        {
                            "id": "step-2",
                            "index": 2,
                            "title": "Autonomous Execution",
                            "description": "Perform necessary edits, tools invocations, and tests."
                        },
                        {
                            "id": "step-3",
                            "index": 3,
                            "title": "Verify & Generate Outputs",
                            "description": "Verify changes and finalize git changeset patch."
                        }
                    ]
                }
            }
        }
        await record_activity(plan_activity, originator="agent")

        # 4. Prepare Agent Loop execution environment
        session_mgr = SessionManager()
        trust_store = ProjectTrustStore()
        loader = ResourceLoader(workspace_cwd)
        cognito_session_id = session_mgr.create(workspace_cwd)

        # Link cognito_session_id in DBJulesSession
        async with async_session_factory() as db:
            sess_res = await db.execute(select(DBJulesSession).where(DBJulesSession.session_id == session_id))
            db_session = sess_res.scalars().first()
            if db_session:
                db_session.cognito_session_id = cognito_session_id
                await db.commit()

        # Tools and context
        extension_registry.refresh("project_local", workspace_cwd, backend_router, semantic_orchestrator)
        tools = extension_registry.tools_for(workspace_cwd)

        context = ToolContext(
            cwd=workspace_cwd,
            trusted=trust_store.is_trusted(workspace_cwd),
            protected_files=loader.get_effective_protected_files()
        )

        model_params = {
            "model": "deepseek-r1:14b",
            "temperature": 0.4,
            "max_tokens": 4096
        }

        await steering_manager.sync_pending_steering_async(cognito_session_id, session_mgr)
        steering_queue = steering_manager.get_queue(cognito_session_id)
        history_lock = steering_manager.get_lock(cognito_session_id)

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are the Jules Unattended Autonomous Agent in Cognito Stack. "
                    f"You are executing an autonomous development task for repository '{source or 'local'}'. "
                    f"Follow plan steps methodically, verify your work, and produce clean changes."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        async with history_lock:
            for m in messages:
                await session_mgr.append_message_async(cognito_session_id, m["role"], m.get("content", ""))

        accumulated_assistant_text = ""
        current_artifacts = []
        is_successful = True
        error_msg = None

        try:
            async for event in agent_loop(
                messages=messages,
                tools=tools,
                context=context,
                backend_router=backend_router,
                model_params=model_params,
                max_turns=12,
                steering_queue=steering_queue,
                history_lock=history_lock,
                session_manager=session_mgr,
                session_id=cognito_session_id,
                steering_manager=steering_manager,
                planning_phase=False  # Unattended mode executes directly
            ):
                if isinstance(event, TextDeltaEvent):
                    accumulated_assistant_text += event.content
                elif isinstance(event, ToolCallEvent):
                    logger.info(f"🔧 [JulesEngine] Tool Call: {event.tool_name}({event.arguments})")
                elif isinstance(event, ToolResultEvent):
                    logger.info(f"📋 [JulesEngine] Tool Result: {event.tool_name}")
                    if event.tool_name == "bash":
                        bash_artifact = {
                            "bashOutput": {
                                "command": str(event.arguments.get("command", "")) if hasattr(event, "arguments") and event.arguments else "",
                                "output": event.output[:4000],
                                "exitCode": 1 if event.is_error else 0
                            }
                        }
                        current_artifacts.append(bash_artifact)
                        await record_activity({
                            "id": f"act-prog-{uuid.uuid4().hex[:8]}",
                            "progressUpdated": {},
                            "artifacts": [bash_artifact]
                        }, originator="agent")
                elif isinstance(event, ErrorEvent):
                    logger.error(f"❌ [JulesEngine] Agent Error: {event.message}")
                    is_successful = False
                    error_msg = event.message
                elif isinstance(event, DoneEvent):
                    logger.info(f"✅ [JulesEngine] Agent Loop Completed. Reason: {event.stop_reason}")

        except Exception as e:
            logger.error(f"❌ [JulesEngine] Execution Exception: {e}", exc_info=True)
            is_successful = False
            error_msg = str(e)

        # 5. Emit agentMessaged if assistant generated reasoning/summary
        if accumulated_assistant_text.strip():
            await record_activity({
                "id": f"act-summary-{uuid.uuid4().hex[:8]}",
                "agentMessaged": {
                    "agentMessage": accumulated_assistant_text.strip()
                }
            }, originator="agent")

        # 6. Capture git diff and outputs
        unidiff, base_commit = get_git_diff_and_base_commit(workspace_cwd)
        outputs = []
        if unidiff:
            patch_output = {
                "changeSet": {
                    "source": source or f"sources/local/{Path(workspace_cwd).name}",
                    "gitPatch": {
                        "unidiffPatch": unidiff,
                        "baseCommitId": base_commit or "0000000000000000",
                        "suggestedCommitMessage": title or f"Autonomous update for: {prompt[:60]}"
                    }
                }
            }
            outputs.append(patch_output)

            # Record activity with changeSet artifact
            await record_activity({
                "id": f"act-patch-{uuid.uuid4().hex[:8]}",
                "agentMessaged": {
                    "agentMessage": f"Changes produced and formatted as unified git diff."
                },
                "artifacts": [patch_output["changeSet"]]
            }, originator="agent")

        # 7. Finalize session state and completion activity
        final_state = "COMPLETED" if is_successful else "FAILED"
        final_iso = now_iso()

        if is_successful:
            await record_activity({
                "id": f"act-finish-{uuid.uuid4().hex[:8]}",
                "sessionCompleted": {}
            }, originator="system")
        else:
            await record_activity({
                "id": f"act-fail-{uuid.uuid4().hex[:8]}",
                "sessionFailed": {
                    "reason": error_msg or "Unknown execution error"
                }
            }, originator="system")

        async with async_session_factory() as db:
            sess_res = await db.execute(select(DBJulesSession).where(DBJulesSession.session_id == session_id))
            db_session = sess_res.scalars().first()
            if db_session:
                payload = dict(db_session.payload)
                payload["state"] = final_state
                payload["updateTime"] = final_iso
                if outputs:
                    payload["outputs"] = outputs
                db_session.payload = payload
                db_session.state = final_state
                db_session.update_time = final_iso
                await db.commit()

        logger.info(f"🏁 Jules session {session_id} ended with state: {final_state}")

jules_unattended_engine = JulesUnattendedEngine()
