# connect-core - Instructions for GitHub Copilot
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.zh-cn.md)


## Project Summary

**connect-core** is an AI automation platform that integrates:
- **n8n**: Workflow orchestrator
- **Ollama**: Local LLM models
- **Whisper**: Speech-to-Text
- **Kokoro**: Text-to-Speech
- **Qdrant**: Vector database
- **Matrix**: Federated messaging
- **Forgejo**: Git hosting

## Service Architecture

### Core Services (Always active)
```
PostgreSQL → Main database
    ↓
Redis → Cache and sessions
    ↓
Qdrant → Vector embeddings
    ↓
Ollama → LLM inference
    ↓
n8n → Workflow orchestration
```

### Voice Services (Profile: voice)
```
Whisper STT ← Audio input
    ↓
n8n workflows
    ↓
Kokoro TTS → Audio output
```

### Optional Services
- **Monitoring**: Prometheus + Grafana + Loki
- **Zrok**: Secure public tunnel
- **ComfyUI**: Image generation

---

## Critical Commands

### First Initialization (MANDATORY)

```bash
# 1. Generate secrets (once)
./scripts/generate-secrets.sh

# 2. Build custom images (ALWAYS FIRST)
docker compose --profile gpu-nvidia --profile voice build

# 3. Verify build
docker images | grep local/

# 4. Start services
docker compose --profile gpu-nvidia --profile voice up -d

# 5. Verify status
docker compose ps
docker compose logs -f n8n
```

### Daily Development

```bash
# View logs of a service
docker compose logs -f [service]

# Restart a service
docker compose restart [service]

# Rebuild after changes in Dockerfile
docker compose build --no-cache [service]
docker compose up -d [service]

# Stop everything
docker compose down

# Stop and clean volumes (DANGER: deletes data)
docker compose down -v
```

### Available Profiles

```bash
# GPU NVIDIA + Voice
docker compose --profile gpu-nvidia --profile voice up -d

# CPU only (without GPU)
docker compose --profile cpu --profile voice-cpu up -d

# AMD GPU
docker compose --profile gpu-amd up -d

# With monitoring
docker compose --profile gpu-nvidia --profile voice --profile monitoring up -d

# With Zrok tunnel
docker compose --profile gpu-nvidia --profile voice --profile zrok up -d
```

---

## Consistency Rules

### When Modifying docker-compose.yml

1. **Services with `build:`** ALWAYS need:
   ```yaml
   build:
     context: .
     dockerfile: Dockerfile.service
   image: local/service:tag
   pull_policy: build  # Optional but recommended
   ```

2. **Services with GPU** ALWAYS need:
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

3. **Services with secrets** ALWAYS need:
   ```yaml
   secrets:
     - secret_name
   environment:
     - VARIABLE_FILE=/run/secrets/secret_name
   ```

### When Creating New Services

1. **Add healthcheck** for critical services
2. **Limit resources** with `deploy.resources.limits`
3. **Use internal networks** (`backend`, `ai`) for non-public services
4. **Add structured logging** (json-file with rotation)
5. **Apply security hardening**:
   ```yaml
   security_opt:
     - no-new-privileges:true
   cap_drop:
     - ALL
   cap_add:
     - [ONLY_NECESSARY_CAPABILITIES]
   ```

---

## Quick Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `pull access denied for local/*` | Image not built | `docker compose build` first |
| `failed to resolve source metadata` | Base image does not exist | Verify version on Docker Hub |
| `connection refused` in healthcheck | Service not started | Check logs: `docker compose logs [service]` |
| `secret not found` | File in `./secrets/` missing | Run `./scripts/generate-secrets.sh` |
| GPU not detected | NVIDIA driver not installed | Install `nvidia-container-toolkit` |

---

## Solution Patterns

### Problem: Service does not start

```bash
# 1. View full logs
docker compose logs [service] --tail=100

# 2. Verify dependencies
docker compose ps | grep -E 'postgres|redis|qdrant'

# 3. Verify secrets
ls -la secrets/

# 4. Enter container for debugging
docker compose exec [service] /bin/sh
```

### Problem: Volume permission error

```bash
# 1. Verify ownership
docker compose exec [service] ls -la /path/to/volume

# 2. Fix permissions (if necessary)
sudo chown -R $(id -u):$(id -g) ./volumes/[service]
```

### Problem: GPU not detected

```bash
# 1. Verify driver
nvidia-smi

# 2. Verify Docker runtime
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi

# 3. If it fails, reinstall nvidia-container-toolkit
```

---

## Critical Environment Variables

### Mandatory (in .env)

```bash
# Database
POSTGRES_USER=n8n_user
POSTGRES_PASSWORD=<generated>
POSTGRES_DB=n8n_db

# n8n
N8N_ENCRYPTION_KEY=<generated>
N8N_RUNNERS_AUTH_TOKEN=<generated>
WEBHOOK_URL=https://n8n.your-domain.com

# Domains (for nginx-proxy)
N8N_DOMAIN=n8n.localhost
OLLAMA_DOMAIN=ollama.localhost
FORGEJO_DOMAIN=forgejo.localhost
```

### Optional

```bash
# Ollama models (downloaded at start)
OLLAMA_MODEL_1=llama3:8b
OLLAMA_MODEL_2=nomic-embed-text

# Whisper model
ASR_MODEL=base.en

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<generated>
```

---

## Quick References

- **Full documentation**: `./docs/README.md`
- **Advanced troubleshooting**: `./docs/WHISPER_TROUBLESHOOTING.md`
- **Useful scripts**: `./scripts/`
- **Configurations**: `./config/`
- **Logs**: `./logs/[service]/`

---

## Image Base Version Validation

### ⚠️ KNOWN ISSUE: Obsolete Base Images

**Problem:** Base image versions in Dockerfiles may not be available if:
- Future versions are specified (e.g.: `25.01` when we are still in `24.12`)
- Images are removed from public registries
- Tags are renamed or deprecated

**Quick fix before building:**

```bash
# See which images are used
grep -h "^FROM " Dockerfile* | sort -u

# If there are "not found" errors, update version and retry
docker compose build --no-cache
```

**Known stable versions (Jan 2026):**
- `nvcr.io/nvidia/pytorch:24.12-py3` ✅
- `ollama/ollama:0.2.1` ✅
- `qdrant/qdrant:v1.9.2` ✅
- `python:3.11-slim` (for LibreTranslate, via pip) ✅
- `erikvl87/languagetool:6.4` ✅

**Problematic versions:**
- `nvcr.io/nvidia/pytorch:25.01-py3` ❌ DOES NOT EXIST (future version)
- `libretranslate/libretranslate:1.6.1` ❌ NOT FOUND
- `libretranslate/libretranslate:1.5.0` ❌ NOT FOUND (official image removed)

**Implemented solution for LibreTranslate:**
- Switched to `python:3.11-slim` + `pip install libretranslate`
- More reliable and automatically maintained
- See [docs/LIBRETRANSLATE_TROUBLESHOOTING.md](../docs/LIBRETRANSLATE_TROUBLESHOOTING.md)

**If you encounter "failed to resolve source metadata" error:**
```bash
# 1. Verify available version on Docker Hub
# Example for images: https://hub.docker.com/r/name/image/tags

# 2. Update Dockerfile (if applicable)
sed -i 's/OLD_VERSION/NEW_VERSION/g' Dockerfile.service

# 3. Rebuild
docker compose build --no-cache [service]
```

---

## Notes for GitHub Copilot

- **ALWAYS build before starting** services with `local/*` images
- **Profiles are mutually exclusive**: use `gpu-nvidia` OR `cpu`, not both
- **Secrets are files**, not direct environment variables
- **Healthchecks have `start_period`**: wait before diagnosing failures
- **Named volumes** persist between restarts, **bind mounts** reflect immediate changes
- **Image versions**: Always use LTS/stable versions, not future ones
- **LibreTranslate**: Uses Python + pip instead of official Docker image (more reliable)
