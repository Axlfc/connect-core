# Kokoro TTS con soporte Blackwell (RTX 50 series)
FROM nvcr.io/nvidia/pytorch:25.03-py3

ENV DEBIAN_FRONTEND=noninteractive

# SALTAMOS EL BLOQUEO DE ENTORNO EXTERNAMENTE GESTIONADO
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar 'uv'
ADD https://astral.sh/uv/install.sh /install_uv.sh
RUN sh /install_uv.sh && rm /install_uv.sh
ENV PATH="/root/.local/bin/:$PATH"

# Directorio de trabajo
WORKDIR /app

# Clonar el repositorio
RUN git clone https://github.com/remsky/Kokoro-FastAPI.git . && \
    git checkout 3af45719940c915b53ad2a63f9cdb6f22680d276

# Instalar dependencias usando uv
# PEP 668: uv también respeta el bloqueo, así que usamos --break-system-packages
RUN uv pip install --system --break-system-packages --no-cache .
RUN uv pip install --system --break-system-packages fastapi uvicorn

# Descargar el modelo
RUN python docker/scripts/download_model.py --output api/src/models/v1_0

# Exponer puerto
EXPOSE 8880

# Variables de entorno
ENV API_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# Iniciar el servidor
CMD ["python", "-m", "uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8880", "--workers", "1"]
