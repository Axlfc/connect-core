FROM python:3.9-slim

WORKDIR /app

# Dependencias de sistema básicas
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar requerimientos desde lockfile con hashes
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Copiar el código
# Se asume que en el host tienes: cognito-backend/app/main.py
COPY . .

# Crear usuario no-root y asignar propiedad
RUN useradd -ms /bin/bash -u 10001 cognito && \
    chown -R cognito:cognito /app

USER cognito

# --- FIX CRÍTICO ---
ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Ejecutamos uvicorn apuntando al módulo app.main
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
