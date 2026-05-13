import whisper
import os
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper STT Server",
    description="Speech-to-Text service powered by OpenAI Whisper",
    version="1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cargar modelo al inicio
MODEL_NAME = os.getenv("ASR_MODEL", "base.en")
CACHE_DIR = os.getenv("WHISPER_CACHE_DIR", "/home/whisper/.cache/whisper")
logger.info(f"Loading Whisper model: {MODEL_NAME} from {CACHE_DIR}")

try:
    model = whisper.load_model(MODEL_NAME, download_root=CACHE_DIR)
    logger.info("✓ Model loaded successfully")
    MODEL_READY = True
except Exception as e:
    logger.error(f"✗ Failed to load model: {e}")
    MODEL_READY = False
    model = None

@app.get("/")
async def root():
    return {
        "service": "Whisper STT",
        "model": MODEL_NAME,
        "status": "ready" if MODEL_READY else "error",
        "documentation": "/docs"
    }

@app.get("/health")
async def health():
    if not MODEL_READY:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": "Model not loaded"}
        )
    return {"status": "healthy", "model": MODEL_NAME}

@app.post("/asr")
@app.post("/inference")
async def transcribe(
    audio_file: UploadFile = File(...),
    task: str = Form("transcribe"),
    language: str = Form("en")
):
    if not MODEL_READY:
        return JSONResponse(
            status_code=503,
            content={"error": "Model not ready"}
        )
    
    try:
        logger.info(f"Transcribing: {audio_file.filename} (task={task}, language={language})")
        
        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            content = await audio_file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Transcribir
        result = model.transcribe(tmp_path, language=language, task=task)
        
        # Limpiar
        os.unlink(tmp_path)
        
        logger.info(f"✓ Transcription completed: {len(result['text'])} chars")
        
        return JSONResponse({
            "text": result["text"],
            "segments": result.get("segments", []),
            "language": result.get("language", language)
        })
    
    except Exception as e:
        logger.error(f"✗ Transcription error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    if not MODEL_READY:
        logger.error("Model failed to load. Server starting in degraded mode.")
        sys.exit(1)
    
    import uvicorn
    logger.info("Starting server on 0.0.0.0:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
