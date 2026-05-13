# Base image supports Nvidia CUDA but does not require it and can also run demucs on the CPU
FROM nvidia/cuda:12.6.2-base-ubuntu22.04

# Set environment variables
ENV TORCH_HOME=/data/models \
    OMP_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1

# Install required system tools and clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    python3 \
    python3-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Clone Demucs from the author's official repository at a specific, stable commit
RUN git clone --single-branch --branch main https://github.com/adefossez/demucs /lib/demucs
WORKDIR /lib/demucs
RUN git checkout b9ab48cad45976ba42b2ff17b229c071f0df9390

# Install demucs and its dependencies with versions known to be compatible
RUN python3 -m pip install --no-cache-dir -e . "torch<2" "torchaudio<2" "numpy<2"

# Pre-download the default model to avoid delays on first run
RUN python3 -m demucs -d cpu --out /tmp/preheat_out /lib/demucs/test.mp3
RUN rm -rf /tmp/preheat_out

# Create and set up the app directory
WORKDIR /app
COPY ./demucs-service/requirements.txt /app/
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY ./demucs-service/main.py /app/

# Expose the port the app runs on
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
