import whisper
import os
import torch
import tempfile
import logging
import gc
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Whisper-On-Demand")

app = FastAPI(
    title="Whisper STT Under-Demand",
    description="Servidor optimizado para liberar VRAM tras cada uso"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables de entorno
MODEL_NAME = os.getenv("ASR_MODEL", "medium") # Recomendado 'medium' para Blackwell
CACHE_DIR = os.getenv("WHISPER_CACHE_DIR", "/home/whisper/.cache/whisper")

@app.get("/health")
async def health():
    # Comprobamos si la GPU está disponible para dar confianza
    cuda_status = torch.cuda.is_available()
    return {
        "status": "healthy",
        "gpu_available": cuda_status,
        "device_name": torch.cuda.get_device_name(0) if cuda_status else "CPU"
    }

@app.post("/asr")
@app.post("/inference")
async def transcribe(
    audio_file: UploadFile = File(...),
    task: str = Form("transcribe"),
    language: str = Form(None)
):
    tmp_path = None
    try:
        logger.info(f"--- Nueva petición recibida: {audio_file.filename} ---")
        
        # 1. Guardar audio temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            content = await audio_file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 2. CARGA DINÁMICA DEL MODELO EN GPU
        logger.info(f"🚀 Cargando modelo {MODEL_NAME} en Blackwell...")
        # device="cuda" fuerza el uso de la GPU 5070
        model = whisper.load_model(MODEL_NAME, device="cuda", download_root=CACHE_DIR)

        # 3. TRANSCRIPCIÓN
        logger.info("🎙️ Transcribiendo...")
        result = model.transcribe(tmp_path, language=language, task=task)

        # 4. LIMPIEZA AGRESIVA DE VRAM
        logger.info("🧹 Liberando memoria de la GPU...")
        
        # Eliminar el objeto del modelo
        del model
        
        # Forzar el recolector de basura de Python
        gc.collect()
        
        # Vaciar el caché de PyTorch específicamente en la GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            
        logger.info("✅ VRAM Liberada correctamente.")

        return JSONResponse({
            "text": result["text"],
            "language": result.get("language"),
            "vram_status": "cleaned"
        })

    except Exception as e:
        logger.error(f"❌ Error en el proceso: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
    finally:
        # Limpiar archivo temporal
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)