import os
import signal
import asyncio
import logging
from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, ai_agents
from app.api.routes.openai_compat import router as openai_router

logger = logging.getLogger("cognito.backend.main")

# Global flag to signal shutdown state
shutdown_event = asyncio.Event()

def handle_sigterm(signum, frame):
    """
    Handler for SIGTERM signal using Python standard signal module.
    Sets shutdown_event to trigger graceful cleanup.
    """
    logger.info(f"Received SIGTERM signal (signum={signum}). Initiating graceful shutdown...")
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(shutdown_event.set)
    except RuntimeError:
        # Loop might not be running yet or already closed
        shutdown_event.set()

# Register SIGTERM signal handler
try:
    signal.signal(signal.SIGTERM, handle_sigterm)
except (ValueError, AttributeError) as e:
    logger.warning(f"Failed to register SIGTERM handler: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    from app.core.sandbox import is_sandbox_disabled_dev_only
    is_sandbox_disabled_dev_only()

    from app.core.extensions.registry import extension_registry
    from app.services.backend_router import backend_router
    from app.services.semantic_orchestrator import semantic_orchestrator

    extension_registry.refresh("global", None, backend_router, semantic_orchestrator)
    extension_registry.refresh("configured", None, backend_router, semantic_orchestrator)

    yield

    # Shutdown logic
    logger.info("Executing graceful shutdown tasks for cognito-backend...")
    # Clean up active resources/sessions if needed
    logger.info("Cognito backend graceful shutdown complete.")


# CSRF PROTECTION NOTE (AUD-004):
# Cognito uses stateless Bearer authentication (Authorization headers) or token-based MCP authentication.
# Since Cognito does NOT rely on browser session cookies or cookie-based ambient credentials for endpoint
# authentication, CSRF (Cross-Site Request Forgery) attacks do not apply to these APIs.
# If cookie-based authentication is added in the future, anti-CSRF tokens (or SameSite cookie controls) must be implemented.

def get_allowed_origins() -> List[str]:
    """
    Retrieves the allowed origins whitelist for CORS and WebSocket validation.
    Layered resolution: Environment Variable COGNITO_ALLOWED_ORIGINS -> standard defaults.
    Never defaults to wildcard '*' combined with credentials.
    """
    raw_origins = os.getenv("COGNITO_ALLOWED_ORIGINS", "")
    if raw_origins.strip():
        origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    else:
        # Default whitelist for safe development and standard clients
        origins = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:5173",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:5173",
        ]
    return origins

# Create the FastAPI app instance
app = FastAPI(
    title="Cognito Stack AI Agent API",
    description="An API for interacting with an AI-powered reasoning engine.",
    version="1.0.0",
    lifespan=lifespan
)

allowed_origins = get_allowed_origins()

# CORS Middleware with explicit whitelist (never wildcard '*' with credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin"],
)

def is_origin_allowed(origin: str, allowed_list: List[str]) -> bool:
    """
    Validates if an Origin header value is present in the allowed origins list.
    """
    if not origin:
        return False
    normalized_origin = origin.rstrip("/")
    for allowed in allowed_list:
        if allowed == "*" or normalized_origin == allowed.rstrip("/"):
            return True
    return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint with strict Origin header validation.
    Rejects connections from unauthorized origins.
    """
    origin = websocket.headers.get("origin")
    allowed_list = get_allowed_origins()

    if not origin or not is_origin_allowed(origin, allowed_list):
        logger.warning(f"WebSocket connection rejected: unauthorized origin '{origin}'")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized Origin")
        return

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

# Include the API routers
app.include_router(health.router, tags=["Health"])
app.include_router(ai_agents.router, prefix="/api", tags=["AI Agents"])
app.include_router(openai_router)          # monta /v1/models y /v1/chat/completions

@app.get("/")
async def root():
    """
    Root endpoint providing basic information about the API.
    """
    return {"message": "Welcome to the Cognito Stack AI Agent API"}
