FROM nvidia/cuda:12.6.2-base-ubuntu22.04

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN uv pip install --system openai-whisper fastapi uvicorn[standard] python-multipart

WORKDIR /home/whisper
COPY server.py .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
