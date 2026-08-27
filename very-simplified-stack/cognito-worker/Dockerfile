FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . .

RUN useradd -ms /bin/bash -u 10001 cognito && \
    chown -R cognito:cognito /app

USER cognito

ENV PYTHONPATH=/app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/v1/health || exit 1

CMD ["uvicorn", "worker_app.main:app", "--host", "0.0.0.0", "--port", "8001"]
