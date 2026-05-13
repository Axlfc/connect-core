# Cognito Stack - Instrucciones para GitHub Copilot
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.zh-cn.md)


## Resumen del Proyecto

**cognito-stack** es una plataforma de automatización con IA que integra:
- **n8n**: Orquestador de workflows
- **Ollama**: Modelos LLM locales
- **Whisper**: Speech-to-Text
- **Kokoro**: Text-to-Speech
- **Qdrant**: Vector database
- **Matrix**: Mensajería federada
- **Forgejo**: Git hosting

## Arquitectura de Servicios

### Servicios Core (Siempre activos)
```
PostgreSQL → Base de datos principal
    ↓
Redis → Cache y sesiones
    ↓
Qdrant → Vector embeddings
    ↓
Ollama → LLM inference
    ↓
n8n → Workflow orchestration
```

### Servicios de Voz (Profile: voice)
```
Whisper STT ← Audio input
    ↓
n8n workflows
    ↓
Kokoro TTS → Audio output
```

### Servicios Opcionales
- **Monitoring**: Prometheus + Grafana + Loki
- **Zrok**: Túnel público seguro
- **ComfyUI**: Generación de imágenes

---

## Comandos Críticos

### Primera Inicialización (OBLIGATORIO)

```bash
# 1. Generar secrets (una sola vez)
./scripts/generate-secrets.sh

# 2. Construir imágenes personalizadas (SIEMPRE PRIMERO)
docker compose --profile gpu-nvidia --profile voice build

# 3. Verificar construcción
docker images | grep local/

# 4. Iniciar servicios
docker compose --profile gpu-nvidia --profile voice up -d

# 5. Verificar estado
docker compose ps
docker compose logs -f n8n
```

### Desarrollo Diario

```bash
# Ver logs de un servicio
docker compose logs -f [servicio]

# Reiniciar un servicio
docker compose restart [servicio]

# Reconstruir tras cambios en Dockerfile
docker compose build --no-cache [servicio]
docker compose up -d [servicio]

# Detener todo
docker compose down

# Detener y limpiar volúmenes (PELIGRO: borra datos)
docker compose down -v
```

### Perfiles Disponibles

```bash
# GPU NVIDIA + Voice
docker compose --profile gpu-nvidia --profile voice up -d

# CPU only (sin GPU)
docker compose --profile cpu --profile voice-cpu up -d

# AMD GPU
docker compose --profile gpu-amd up -d

# Con monitoring
docker compose --profile gpu-nvidia --profile voice --profile monitoring up -d

# Con túnel Zrok
docker compose --profile gpu-nvidia --profile voice --profile zrok up -d
```

---

## Reglas de Coherencia

### Al Modificar docker-compose.yml

1. **Servicios con `build:`** SIEMPRE necesitan:
   ```yaml
   build:
     context: .
     dockerfile: Dockerfile.servicio
   image: local/servicio:tag
   pull_policy: build  # Opcional pero recomendado
   ```

2. **Servicios con GPU** SIEMPRE necesitan:
   ```yaml
   profiles: ["gpu-nvidia"]
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```

3. **Servicios con secrets** SIEMPRE necesitan:
   ```yaml
   secrets:
     - nombre_secret
   environment:
     - VARIABLE_FILE=/run/secrets/nombre_secret
   ```

### Al Crear Nuevos Servicios

1. **Añadir healthcheck** para servicios críticos
2. **Limitar recursos** con `deploy.resources.limits`
3. **Usar redes internas** (`backend`, `ai`) para servicios no públicos
4. **Añadir logging estructurado** (json-file con rotación)
5. **Aplicar security hardening**:
   ```yaml
   security_opt:
     - no-new-privileges:true
   cap_drop:
     - ALL
   cap_add:
     - [SOLO_CAPABILITIES_NECESARIAS]
   ```

---

## Troubleshooting Rápido

| Error | Causa | Solución |
|-------|-------|----------|
| `pull access denied for local/*` | Imagen no construida | `docker compose build` primero |
| `failed to resolve source metadata` | Imagen base no existe | Verificar versión en Docker Hub |
| `connection refused` en healthcheck | Servicio no iniciado | Revisar logs: `docker compose logs [servicio]` |
| `secret not found` | Archivo en `./secrets/` falta | Ejecutar `./scripts/generate-secrets.sh` |
| GPU no detectada | Driver NVIDIA no instalado | Instalar `nvidia-container-toolkit` |

---

## Patrones de Solución

### Problema: Servicio no inicia

```bash
# 1. Ver logs completos
docker compose logs [servicio] --tail=100

# 2. Verificar dependencias
docker compose ps | grep -E 'postgres|redis|qdrant'

# 3. Verificar secrets
ls -la secrets/

# 4. Entrar al contenedor para debug
docker compose exec [servicio] /bin/sh
```

### Problema: Error de permisos en volúmenes

```bash
# 1. Verificar ownership
docker compose exec [servicio] ls -la /path/to/volume

# 2. Corregir permisos (si necesario)
sudo chown -R $(id -u):$(id -g) ./volumes/[servicio]
```

### Problema: GPU no detectada

```bash
# 1. Verificar driver
nvidia-smi

# 2. Verificar runtime de Docker
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi

# 3. Si falla, reinstalar nvidia-container-toolkit
```

---

## Variables de Entorno Críticas

### Obligatorias (en .env)

```bash
# Base de datos
POSTGRES_USER=n8n_user
POSTGRES_PASSWORD=<generado>
POSTGRES_DB=n8n_db

# n8n
N8N_ENCRYPTION_KEY=<generado>
N8N_RUNNERS_AUTH_TOKEN=<generado>
WEBHOOK_URL=https://n8n.tu-dominio.com

# Dominios (para nginx-proxy)
N8N_DOMAIN=n8n.localhost
OLLAMA_DOMAIN=ollama.localhost
FORGEJO_DOMAIN=forgejo.localhost
```

### Opcionales

```bash
# Ollama models (se descargan al iniciar)
OLLAMA_MODEL_1=llama3:8b
OLLAMA_MODEL_2=nomic-embed-text

# Whisper model
ASR_MODEL=base.en

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<generado>
```

---

## Referencias Rápidas

- **Documentación completa**: `./docs/README.md`
- **Troubleshooting avanzado**: `./docs/WHISPER_TROUBLESHOOTING.md`
- **Scripts útiles**: `./scripts/`
- **Configuraciones**: `./config/`
- **Logs**: `./logs/[servicio]/`

---

## Validación de Versiones de Imágenes Base

### ⚠️ ISSUE CONOCIDO: Imágenes Base Obsoletas

**Problema:** Las versiones de imágenes base en los Dockerfiles pueden no estar disponibles si:
- Versiones futuras son especificadas (ej: `25.01` cuando aún estamos en `24.12`)
- Imágenes son removidas de registros públicos
- Tags son renombrados o deprecated

**Solución rápida antes de hacer build:**

```bash
# Ver qué imágenes se usan
grep -h "^FROM " Dockerfile* | sort -u

# Si hay errores "not found", actualizar versión y reintentar
docker compose build --no-cache
```

**Versiones conocidas como estables (Jan 2026):**
- `nvcr.io/nvidia/pytorch:24.12-py3` ✅
- `ollama/ollama:0.2.1` ✅
- `qdrant/qdrant:v1.9.2` ✅
- `python:3.11-slim` (para LibreTranslate, vía pip) ✅
- `erikvl87/languagetool:6.4` ✅

**Versiones problemáticas:**
- `nvcr.io/nvidia/pytorch:25.01-py3` ❌ NO EXISTE (versión futura)
- `libretranslate/libretranslate:1.6.1` ❌ NO ENCONTRADA
- `libretranslate/libretranslate:1.5.0` ❌ NO ENCONTRADA (imagen oficial removida)

**Solución implementada para LibreTranslate:**
- Cambio a `python:3.11-slim` + `pip install libretranslate`
- Más confiable y se mantiene automáticamente
- Ver [docs/LIBRETRANSLATE_TROUBLESHOOTING.md](../docs/LIBRETRANSLATE_TROUBLESHOOTING.md)

**Si encuentras error "failed to resolve source metadata":**
```bash
# 1. Verificar versión disponible en Docker Hub
# Ejemplo para imágenes: https://hub.docker.com/r/nombre/imagen/tags

# 2. Actualizar Dockerfile (si aplica)
sed -i 's/VERSION_VIEJA/VERSION_NUEVA/g' Dockerfile.servicio

# 3. Reconstruir
docker compose build --no-cache [servicio]
```

---

## Notas para GitHub Copilot

- **SIEMPRE construir antes de iniciar** servicios con `local/*` images
- **Perfiles son excluyentes**: usa `gpu-nvidia` O `cpu`, no ambos
- **Secrets son archivos**, no variables de entorno directas
- **Healthchecks tienen `start_period`**: esperar antes de diagnosticar fallos
- **Volúmenes nombrados** persisten entre reinicios, **bind mounts** reflejan cambios inmediatos
- **Versiones de imágenes**: Usar siempre versiones LTS/estables, no futures
- **LibreTranslate**: Usa Python + pip en lugar de imagen Docker oficial (más confiable)
