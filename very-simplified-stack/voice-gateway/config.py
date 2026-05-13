import os

# Check both possible Whisper ports (9000 for official image, 8080 for custom)
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper-stt:9000")
KOKORO_URL = os.getenv("KOKORO_URL", "http://kokoro-tts:8880")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
VOICE_CACHE_TTL = int(os.getenv("VOICE_CACHE_TTL", 3600))

# Maximum file upload size (in bytes)
# Defaults to 25MB, as recommended by OpenAI for Whisper.
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 25 * 1024 * 1024))

# Add debug logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Whisper URL: {WHISPER_URL}")
logger.info(f"Kokoro URL: {KOKORO_URL}")
logger.info(f"Ollama URL: {OLLAMA_URL}")
logger.info(f"Redis URL: {REDIS_URL}")