"""
openai_compat.py

Exposes the Cognito Stack AI router as an OpenAI-compatible API.

Modelos disponibles:
  - cognito              → ReasoningEngine  (BackendRouter GPU-first failover)
  - cognito-orchestrator → SemanticOrchestrator (planning + multi-backend routing)
                           ⚠ El orquestador no soporta streaming nativo (hace planning
                             en fase 1 antes de ejecutar). Se simula: ejecuta completo
                             y hace fake-stream del resultado token a token.

Endpoints:
  GET  /v1/models                → lista ambos modelos
  GET  /v1/models/{model_id}     → detalle de un modelo
  POST /v1/chat/completions      → enruta al engine correcto según 'model'
                                   soporta stream: true | false

SSE format (stream: true):
  data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":N,"model":"cognito","choices":[{"index":0,"delta":{"role":"assistant","content":"token"},"finish_reason":null}]}
  ...
  data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":N,"model":"cognito","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
  data: [DONE]

Compatible con: Open WebUI, LM Studio, LangChain, cualquier cliente OpenAI-compat.
"""

import asyncio
import json
import time
import uuid
import logging
import math
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.services.reasoning_engine import reasoning_engine
from app.services.semantic_orchestrator import semantic_orchestrator
from app.services.backend_router import backend_router
from app.services.backend_registry import BACKENDS_BY_PRIORITY, BackendType
from app.services.backend_client import BackendClient
from app.models.ai import AIRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["OpenAI-compat"])


# ══════════════════════════════════════════════════════════════════════════════
# Model registry
# ══════════════════════════════════════════════════════════════════════════════

COGNITO_OWNED_BY = "cognito-stack"

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "cognito": {
        "created":     1735000000,
        "description": "GPU-first cascading failover router. Fast and reliable.",
        "engine":      "reasoning",
        "streaming":   True,
    },
    "cognito-orchestrator": {
        "created":     1735000001,
        "description": "Semantic planning orchestrator. Decomposes complex requests into subtasks routed to specialized models.",
        "engine":      "orchestrator",
        "streaming":   True,    # simulated — executes fully then streams result
    },
}


def _get_engine(model_id: str):
    entry = MODEL_REGISTRY.get(model_id)
    if entry is None:
        return None
    if entry["engine"] == "reasoning":
        return reasoning_engine
    if entry["engine"] == "orchestrator":
        return semantic_orchestrator
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════════════════

class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str
    description: Optional[str] = None


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: List[ModelCard]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = "cognito"
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    session_id: Optional[str] = None

    class Config:
        extra = "allow"


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "error"] = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo
    x_cognito: Optional[Dict[str, Any]] = Field(default=None, alias="x-cognito")

    class Config:
        populate_by_name = True


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/models", response_model=ModelList)
async def list_models():
    cards = [
        ModelCard(
            id=model_id,
            created=info["created"],
            owned_by=COGNITO_OWNED_BY,
            description=info["description"],
        )
        for model_id, info in MODEL_REGISTRY.items()
    ]
    return ModelList(data=cards)


@router.get("/models/{model_id}", response_model=ModelCard)
async def get_model(model_id: str):
    info = MODEL_REGISTRY.get(model_id)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found. Available: {list(MODEL_REGISTRY.keys())}",
        )
    return ModelCard(
        id=model_id,
        created=info["created"],
        owned_by=COGNITO_OWNED_BY,
        description=info["description"],
    )


@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    Procesa una conversación:
      - stream=false → respuesta JSON completa (comportamiento anterior)
      - stream=true  → SSE token a token, compatible con OpenAI streaming
    """
    if _get_engine(req.model) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{req.model}' not found. Available: {list(MODEL_REGISTRY.keys())}",
        )

    prompt = _messages_to_prompt(req.messages)
    model_params: Dict[str, Any] = {}
    if req.temperature is not None:
        model_params["temperature"] = req.temperature
    if req.max_tokens is not None:
        model_params["max_tokens"] = req.max_tokens
    if req.top_p is not None:
        model_params["top_p"] = req.top_p

    session_id = req.session_id or str(uuid.uuid4())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    logger.info(
        "[OpenAI-compat] chat/completions | model=%s | stream=%s | session=%s",
        req.model, req.stream, session_id,
    )

    if req.stream:
        return StreamingResponse(
            _stream_response(
                model_id=req.model,
                prompt=prompt,
                model_params=model_params or None,
                session_id=session_id,
                completion_id=completion_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",   # desactiva buffering en nginx
            },
        )

    # ── Blocking path ──────────────────────────────────────────────────────────
    engine = _get_engine(req.model)
    ai_request = AIRequest(
        prompt=prompt,
        session_id=session_id,
        parameters=model_params or None,
    )

    try:
        ai_response = await engine.process_request(ai_request)
    except Exception as e:
        logger.error("[OpenAI-compat] Engine error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Inference error. See server logs.")

    response_obj = ChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        model=req.model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=ai_response.response),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(),
        **{"x-cognito": ai_response.metadata},
    )

    return JSONResponse(
        content=response_obj.model_dump(by_alias=True),
        media_type="application/json; charset=utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Uncertainty Calculation
# ══════════════════════════════════════════════════════════════════════════════

def compute_uncertainty(logprob_data: Any) -> Optional[float]:
    """
    Shannon entropy of the top-k distribution, normalized to [0, 1].
    Expects Ollama-style logprobs data.
    """
    if not logprob_data:
        return None

    top_logprobs = {}
    if isinstance(logprob_data, list) and logprob_data:
        # Ollama returns a list of token info, usually just one for the current token
        entry = logprob_data[0]
        for candidate in entry.get("top_logprobs", []):
            top_logprobs[candidate["token"]] = candidate["logprob"]
    elif isinstance(logprob_data, dict):
        # Already parsed or different format
        top_logprobs = logprob_data

    if not top_logprobs:
        return None

    try:
        probs = [math.exp(lp) for lp in top_logprobs.values()]
        total = sum(probs)
        if total == 0:
            return 0.0
        probs = [p / total for p in probs]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
        return entropy / max_entropy if max_entropy > 0 else 0.0
    except Exception as e:
        logger.error("[Uncertainty] Error computing entropy: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Streaming logic
# ══════════════════════════════════════════════════════════════════════════════

async def _stream_response(
    model_id: str,
    prompt: str,
    model_params: Optional[Dict[str, Any]],
    session_id: str,
    completion_id: str,
) -> AsyncGenerator[str, None]:
    """
    Unified SSE generator.

    - cognito              → streams tokens directly from the backend (true streaming)
    - cognito-orchestrator → runs the full orchestration, then fake-streams the result
                             word by word (the planning phase can't be interrupted)
    """
    created = int(time.time())

    # ── Helper: format one SSE chunk ──────────────────────────────────────────
    def _chunk(content: str, finish_reason: Optional[str] = None, uncertainty: Optional[float] = None) -> str:
        delta = {"content": content} if content else {}
        if uncertainty is not None:
            delta["uncertainty"] = uncertainty

        if finish_reason is None and not content:
            delta = {}
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # ── First chunk: role announcement (OpenAI convention) ────────────────────
    role_payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(role_payload, ensure_ascii=False)}\n\n"

    try:
        if model_id == "cognito-orchestrator":
            # ── Orchestrator: full execution → fake-stream result ──────────────
            ai_request = AIRequest(
                prompt=prompt,
                session_id=session_id,
                parameters=model_params,
            )
            ai_response = await semantic_orchestrator.process(ai_request)
            full_text = ai_response.response

            # Emit word by word with a small delay to simulate streaming feel
            words = full_text.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield _chunk(token)
                await asyncio.sleep(0.01)   # 10ms between words — adjust to taste

        else:
            # ── cognito: true token streaming from backend ─────────────────────
            # Find the first healthy backend client directly
            client = await _get_streaming_client(model_params)
            if client is None:
                raise RuntimeError("No healthy backend available for streaming.")

            async for chunk_data in client.generate_stream(prompt, model_params):
                token = chunk_data.get("token", "")
                logprobs = chunk_data.get("logprobs")
                uncertainty = compute_uncertainty(logprobs)
                yield _chunk(token, uncertainty=uncertainty)

    except Exception as e:
        logger.error("[OpenAI-compat] Streaming error: %s", e, exc_info=True)
        error_payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [{"index": 0, "delta": {"content": f"\n\n[Error: {e}]"}, "finish_reason": "error"}],
        }
        yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── Final chunk: finish_reason=stop ───────────────────────────────────────
    yield _chunk("", finish_reason="stop")
    yield "data: [DONE]\n\n"


async def _get_streaming_client(model_params: Optional[Dict[str, Any]]) -> Optional[BackendClient]:
    """
    Returns the first healthy BackendClient from the priority list.
    Mirrors BackendRouter's failover logic but returns the client
    instead of calling generate(), so we can call generate_stream().
    """
    for config in BACKENDS_BY_PRIORITY:
        client = BackendClient(config)
        if await client.check_health():
            logger.info("[Stream] Using backend '%s'", config.name)
            return client
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _messages_to_prompt(messages: List[ChatMessage]) -> str:
    return "\n\n".join(f"[{msg.role}]\n{msg.content}" for msg in messages)