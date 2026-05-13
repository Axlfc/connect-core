import base64
import hashlib
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import redis
from models import (
    ConversationResponse,
    SpeechRequest,
    TranscriptionResponse,
)
import config

app = FastAPI()

# Configure CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
try:
    redis_client = redis.Redis.from_url(
        config.REDIS_URL, password=config.REDIS_PASSWORD, decode_responses=True
    )
    redis_client.ping()
    print("Successfully connected to Redis")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")
    redis_client = None

# HTTP client
client = httpx.AsyncClient(timeout=120.0)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for the voice gateway.
    """
    return {"status": "ok"}


@app.get("/v1/voices")
async def get_voices():
    """
    Lists the available TTS voices.
    """
    try:
        response = await client.get(f"{config.KOKORO_URL}/v1/audio/voices")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code, detail="Could not fetch voices from Kokoro TTS"
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Kokoro TTS is unavailable")


@app.get("/v1/models")
async def get_models():
    """
    Lists the available LLM models from Ollama.
    """
    try:
        response = await client.get(f"{config.OLLAMA_URL}/api/tags")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code, detail="Could not fetch models from Ollama"
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Ollama is unavailable")


@app.post("/v1/audio/transcriptions", response_model=TranscriptionResponse)
async def create_transcription(file: UploadFile = File(...)):
    """
    Transcribes an audio file using Whisper ASR Webservice.
    """
    contents = await file.read()
    if len(contents) > config.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds limit of {config.MAX_UPLOAD_SIZE // 1024 // 1024}MB.",
        )

    try:
        # Whisper ASR Webservice uses 'audio_file' field and '/asr' endpoint
        files = {"audio_file": (file.filename, contents, file.content_type)}
        response = await client.post(
            f"{config.WHISPER_URL}/asr",
            files=files,
            params={"output": "json"}
        )
        response.raise_for_status()
        result = response.json()

        # Handle different response formats
        if isinstance(result, dict) and "text" in result:
            return {"text": result["text"]}
        elif isinstance(result, str):
            return {"text": result}
        else:
            return {"text": str(result)}
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error from Whisper: {e.response.text}",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Whisper is unavailable: {str(e)}")


@app.post("/v1/audio/speech")
async def create_speech(request: SpeechRequest):
    """
    Generates audio from text using Kokoro TTS (OpenAI-compatible endpoint).
    Caches the result in Redis.
    """
    if redis_client:
        cache_key = f"tts:{hashlib.md5(f'{request.text}{request.voice}'.encode()).hexdigest()}"
        cached_audio = redis_client.get(cache_key)
        if cached_audio:
            return Response(content=base64.b64decode(cached_audio), media_type=f"audio/{request.format}")

    try:
        # Kokoro-FastAPI uses OpenAI-compatible endpoint with "input" field
        payload = {
            "model": "kokoro",  # Required for compatibility
            "input": request.text,
            "voice": request.voice,
            "response_format": request.format,
        }
        if request.speed:
            payload["speed"] = request.speed

        response = await client.post(
            f"{config.KOKORO_URL}/v1/audio/speech",
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()
        audio_data = response.content
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        if redis_client:
            redis_client.setex(cache_key, config.VOICE_CACHE_TTL, audio_base64)

        return Response(content=audio_data, media_type=f"audio/{request.format}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error from Kokoro TTS: {e.response.text}",
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Kokoro TTS is unavailable: {str(e)}")


@app.post("/v1/conversation", response_model=ConversationResponse)
async def conversation(
        file: UploadFile = File(...),
        model: str = Form("llama3.2"),
        voice: str = Form("af_bella"),
):
    """
    Full conversation pipeline: STT -> LLM -> TTS.
    """
    # 1. Transcribe audio to text using Whisper ASR Webservice
    contents = await file.read()
    if len(contents) > config.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds limit of {config.MAX_UPLOAD_SIZE // 1024 // 1024}MB.",
        )

    try:
        files = {"audio_file": (file.filename, contents, file.content_type)}
        stt_response = await client.post(
            f"{config.WHISPER_URL}/asr",
            files=files,
            params={"output": "json"}
        )
        stt_response.raise_for_status()
        stt_data = stt_response.json()

        # Handle different response formats
        if isinstance(stt_data, dict) and "text" in stt_data:
            user_text = stt_data["text"]
        elif isinstance(stt_data, str):
            user_text = stt_data
        else:
            user_text = str(stt_data)

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        raise HTTPException(status_code=503, detail=f"Whisper STT service error: {str(e)}")

    # 2. Get response from LLM
    try:
        llm_payload = {
            "model": model,
            "prompt": user_text,
            "stream": False,
        }
        llm_response = await client.post(
            f"{config.OLLAMA_URL}/api/generate", json=llm_payload
        )
        llm_response.raise_for_status()
        ai_text = llm_response.json()["response"]
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama service error: {str(e)}")

    # 3. Generate speech from LLM response using Kokoro
    try:
        tts_payload = {
            "model": "kokoro",
            "input": ai_text,
            "voice": voice,
            "response_format": "mp3",
        }
        tts_response = await client.post(
            f"{config.KOKORO_URL}/v1/audio/speech",
            json=tts_payload,
            timeout=60.0
        )
        tts_response.raise_for_status()
        audio_data = tts_response.content
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        raise HTTPException(status_code=503, detail=f"Kokoro TTS service error: {str(e)}")

    return ConversationResponse(
        user_text=user_text,
        ai_text=ai_text,
        audio_base64=audio_base64,
    )