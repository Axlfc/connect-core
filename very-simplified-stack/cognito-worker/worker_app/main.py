import os
import json
import signal
import logging
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from worker_app.auth import verify_cognito_request
from worker_app.worktree import GitWorktreeManager
from worker_app.codex import MockCodexProvider, SubprocessCodexProvider
from worker_app.verification import VerificationEngine
from app.core.path_safety import is_path_contained

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cognito.worker")

# Global flag for graceful shutdown handling
shutdown_event = asyncio.Event()

def handle_sigterm(signum, frame):
    """
    Handler for SIGTERM signal using Python standard signal module.
    Sets shutdown_event to trigger graceful cleanup.
    """
    logger.info(f"Received SIGTERM signal (signum={signum}) in worker. Initiating graceful shutdown...")
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except RuntimeError:
        shutdown_event.set()

try:
    signal.signal(signal.SIGTERM, handle_sigterm)
except (ValueError, AttributeError) as e:
    logger.warning(f"Failed to register SIGTERM handler: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Cognito worker starting up...")
    yield
    # Shutdown / cleanup tasks (cancel active jobs, cleanup temporary state)
    logger.info("Executing graceful shutdown tasks for cognito-worker...")
    logger.info("Cognito worker graceful shutdown complete.")


app = FastAPI(
    title="Cognito Host Worker",
    description="Local host-side worker executing tasks in isolated Git worktrees",
    version="1.0.0",
    lifespan=lifespan
)

# ══════════════════════════════════════════════════════════════════════════════
# Config & State
# ══════════════════════════════════════════════════════════════════════════════

WORKER_ID = os.getenv("COGNITO_WORKER_ID", "local-worker-01")
raw_secrets = os.getenv("COGNITO_WORKER_SECRETS")
if not raw_secrets or not raw_secrets.strip():
    raise RuntimeError("COGNITO_WORKER_SECRETS environment variable is required but not set.")
SHARED_SECRETS = [s.strip() for s in raw_secrets.split(",") if s.strip()]
if not SHARED_SECRETS:
    raise RuntimeError("COGNITO_WORKER_SECRETS environment variable is required but empty.")

ALLOWED_ROOTS = [
    os.path.realpath(p.strip())
    for p in os.getenv("ALLOWED_REPOSITORY_ROOTS", "/tmp").split(",")
    if p.strip()
]

# Initialize managers
worktree_manager = GitWorktreeManager()
verification_engine = VerificationEngine()

# Codex Provider selection (fallback to mock if subprocess app server is not found)
use_mock_codex = os.getenv("USE_MOCK_CODEX", "true").lower() == "true"
if use_mock_codex:
    codex_provider = MockCodexProvider()
else:
    codex_provider = SubprocessCodexProvider(os.getenv("CODEX_APP_SERVER_PATH", "codex-app-server"))

# Simple dependency to authenticate requests
async def authenticate(request: Request):
    await verify_cognito_request(request, SHARED_SECRETS, WORKER_ID)

# Helper to validate repository path against allowlist
def validate_repo_path(repo_path: str):
    real_repo = os.path.realpath(repo_path)
    # Check null bytes and safety
    if '\x00' in real_repo:
        raise HTTPException(status_code=400, detail="Null bytes in repository path")

    # Resolve allowed roots containment
    is_allowed = False
    for r in ALLOWED_ROOTS:
        if is_path_contained(real_repo, r):
            is_allowed = True
            break
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Repository path is outside the allowed roots list")
    return real_repo

# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

class TaskRequest(BaseModel):
    task_id: str
    session_id: str
    model: str
    requirements: str
    base_repo_path: str
    repo_id: str
    attempt: int
    environment: Dict[str, Any] = {}

class VerificationRequest(BaseModel):
    task_id: str
    attempt_id: str
    worktree_path: str
    category: str  # test, lint, typecheck

class CleanupRequest(BaseModel):
    base_repo_path: str
    worktree_path: str
    force: bool = False

@app.get("/v1/health")
async def health():
    return {
        "status": "healthy",
        "worker_id": WORKER_ID,
        "allowed_roots": ALLOWED_ROOTS,
        "capabilities": {
            "codex": not use_mock_codex,
            "git_worktrees": True,
            "verification": True
        }
    }

@app.get("/v1/models")
async def get_models(authenticated: Any = Depends(authenticate)):
    models = await codex_provider.discover_models()
    return {"models": models}

@app.post("/v1/task")
async def start_task(req: TaskRequest, authenticated: Any = Depends(authenticate)):
    logger.info(f"Received start task request for task_id={req.task_id} | model={req.model}")

    # Revalidate containment of base repo path
    validated_repo = validate_repo_path(req.base_repo_path)

    # 1. Create Git worktree
    try:
        worktree_path, branch_name = worktree_manager.create_worktree(
            validated_repo, req.repo_id, req.task_id, req.attempt
        )
    except Exception as e:
        logger.error(f"Worktree creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git worktree creation failed: {str(e)}")

    # 2. Return SSE streaming task execution
    async def sse_event_stream():
        # Start announcement
        yield f"data: {json.dumps({'type': 'worktree_created', 'worktree_path': worktree_path, 'branch_name': branch_name})}\n\n"

        try:
            async for event in codex_provider.execute_task(
                req.task_id, req.model, req.requirements, worktree_path, req.environment
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Error during Codex execution: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/v1/verify")
async def verify_task(req: VerificationRequest, authenticated: Any = Depends(authenticate)):
    # Validate containment of worktree path (must be inside allowed roots since it sits inside the worktrees folder)
    # Check null bytes
    if '\x00' in req.worktree_path:
        raise HTTPException(status_code=400, detail="Null bytes in worktree path")

    run_result = await verification_engine.run_verification(
        req.task_id, req.attempt_id, req.worktree_path, req.category
    )
    return run_result

@app.post("/v1/cleanup")
async def cleanup_task(req: CleanupRequest, authenticated: Any = Depends(authenticate)):
    validated_repo = validate_repo_path(req.base_repo_path)
    worktree_manager.cleanup_worktree(validated_repo, req.worktree_path, req.force)
    return {"status": "success", "message": f"Cleaned up worktree {req.worktree_path}"}
