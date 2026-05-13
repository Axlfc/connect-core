from fastapi import FastAPI
from app.api.routes import health, ai_agents
from app.api.routes.openai_compat import router as openai_router

# Create the FastAPI app instance
app = FastAPI(
    title="Cognito Stack AI Agent API",
    description="An API for interacting with an AI-powered reasoning engine.",
    version="1.0.0"
)

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