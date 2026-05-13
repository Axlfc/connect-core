FROM python:3.9-slim

WORKDIR /app

# Dependencias de sistema básicas
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
# Se asume que en el host tienes: cognito-backend/app/main.py
COPY . .

# --- FIX CRÍTICO ---
ENV PYTHONPATH=/app

EXPOSE 8000

# Ejecutamos uvicorn apuntando al módulo app.main
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
