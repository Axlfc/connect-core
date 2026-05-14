# connect-core - Instruccions per a GitHub Copilot
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/.github/copilot-instructions.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/.github/copilot-instructions.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/.github/copilot-instructions.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/.github/copilot-instructions.zh-cn.md)


## Resum del Projecte

**connect-core** és una plataforma d'automatització amb IA que integra:
- **n8n**: Orquestrador de workflows
- **Ollama**: Models LLM locals
- **Whisper**: Speech-to-Text
- **Kokoro**: Text-to-Speech
- **Qdrant**: Vector database
- **Matrix**: Missatgeria federada
- **Forgejo**: Git hosting

## Arquitectura de Serveis

### Serveis Core (Sempre actius)
```
PostgreSQL → Base de dades principal
    ↓
Redis → Memòria cau (cache) i sessions
    ↓
Qdrant → Vector embeddings
    ↓
Ollama → LLM inference
    ↓
n8n → Workflow orchestration
```

### Serveis de Veu (Profile: voice)
```
Whisper STT ← Audio input
    ↓
n8n workflows
    ↓
Kokoro TTS → Audio output
```

### Serveis Opcionals
- **Monitoring**: Prometheus + Grafana + Loki
- **Zrok**: Túnel públic segur
- **ComfyUI**: Generació d'imatges

---

## Comandes Crítiques

### Primera Inicialització (OBLIGATORI)

```bash
# 1. Generar secrets (una sola vegada)
./scripts/generate-secrets.sh

# 2. Construir imatges personalitzades (SEMPRE PRIMER)
docker compose --profile gpu-nvidia --profile voice build

# 3. Verificar construcció
docker images | grep local/

# 4. Iniciar serveis
docker compose --profile gpu-nvidia --profile voice up -d

# 5. Verificar estat
docker compose ps
docker compose logs -f n8n
```

### Desenvolupament Diari

```bash
# Veure logs d'un servei
docker compose logs -f [servei]

# Reiniciar un servei
docker compose restart [servei]

# Reconstruir després de canvis en Dockerfile
docker compose build --no-cache [servei]
docker compose up -d [servei]

# Aturar tot
docker compose down

# Aturar i netejar volums (PERILL: esborra dades)
docker compose down -v
```

### Perfils Disponibles

```bash
# GPU NVIDIA + Voice
docker compose --profile gpu-nvidia --profile voice up -d

# CPU only (sense GPU)
docker compose --profile cpu --profile voice-cpu up -d

# AMD GPU
docker compose --profile gpu-amd up -d

# Amb monitoring
docker compose --profile gpu-nvidia --profile voice --profile monitoring up -d

# Amb túnel Zrok
docker compose --profile gpu-nvidia --profile voice --profile zrok up -d
```

---

## Regles de Coherència

### En Modificar docker-compose.yml

1. **Serveis amb `build:`** SEMPRE necessiten:
   ```yaml
   build:
     context: .
     dockerfile: Dockerfile.servei
   image: local/servei:tag
   pull_policy: build  # Opcional però recomanat
   ```

2. **Serveis amb GPU** SEMPRE necessiten:
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

3. **Serveis amb secrets** SEMPRE necessiten:
   ```yaml
   secrets:
     - nom_secret
   environment:
     - VARIABLE_FILE=/run/secrets/nom_secret
   ```

### En Crear Nous Serveis

1. **Afegir healthcheck** per a serveis crítics
2. **Limitar recursos** amb `deploy.resources.limits`
3. **Utilitzar xarxes internes** (`backend`, `ai`) per a serveis no públics
4. **Afegir logging estructurat** (json-file amb rotació)
5. **Aplicar security hardening**:
   ```yaml
   security_opt:
     - no-new-privileges:true
   cap_drop:
     - ALL
   cap_add:
     - [SOLS_CAPABILITIES_NECESSÀRIES]
   ```

---

## Troubleshooting Ràpid

| Error | Causa | Solució |
|-------|-------|----------|
| `pull access denied for local/*` | Imatge no construïda | `docker compose build` primer |
| `failed to resolve source metadata` | Imatge base no existeix | Verificar versió a Docker Hub |
| `connection refused` en healthcheck | Servei no iniciat | Revisar logs: `docker compose logs [servei]` |
| `secret not found` | Fitxer a `./secrets/` falta | Executar `./scripts/generate-secrets.sh` |
| GPU no detectada | Driver NVIDIA no instal·lat | Instal·lar `nvidia-container-toolkit` |

---

## Patrons de Solució

### Problema: El servei no s'inicia

```bash
# 1. Veure logs complets
docker compose logs [servei] --tail=100

# 2. Verificar dependències
docker compose ps | grep -E 'postgres|redis|qdrant'

# 3. Verificar secrets
ls -la secrets/

# 4. Entrar al contenidor per a depurar
docker compose exec [servei] /bin/sh
```

### Problema: Error de permisos en volums

```bash
# 1. Verificar ownership
docker compose exec [servei] ls -la /path/to/volume

# 2. Corregir permisos (si cal)
sudo chown -R $(id -u):$(id -g) ./volumes/[servei]
```

### Problema: GPU no detectada

```bash
# 1. Verificar driver
nvidia-smi

# 2. Verificar runtime de Docker
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi

# 3. Si falla, reinstal·lar nvidia-container-toolkit
```

---

## Variables d'Entorn Crítiques

### Obligatòries (a .env)

```bash
# Base de dades
POSTGRES_USER=n8n_user
POSTGRES_PASSWORD=<generat>
POSTGRES_DB=n8n_db

# n8n
N8N_ENCRYPTION_KEY=<generat>
N8N_RUNNERS_AUTH_TOKEN=<generat>
WEBHOOK_URL=https://n8n.el-teu-domini.com

# Dominis (per a nginx-proxy)
N8N_DOMAIN=n8n.localhost
OLLAMA_DOMAIN=ollama.localhost
FORGEJO_DOMAIN=forgejo.localhost
```

### Opcionals

```bash
# Ollama models (es descarreguen en iniciar)
OLLAMA_MODEL_1=llama3:8b
OLLAMA_MODEL_2=nomic-embed-text

# Whisper model
ASR_MODEL=base.en

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<generat>
```

---

## Referències Ràpides

- **Documentació completa**: `./docs/README.md`
- **Troubleshooting avançat**: `./docs/WHISPER_TROUBLESHOOTING.md`
- **Scripts útils**: `./scripts/`
- **Configuracions**: `./config/`
- **Logs**: `./logs/[servei]/`

---

## Validació de Versions d'Imatges Base

### ⚠️ ISSUE CONEGUT: Imatges Base Obsoletes

**Problema:** Les versions d'imatges base als Dockerfiles poden no estar disponibles si:
- Versions futures són especificades (ex: `25.01` quan encara som al `24.12`)
- Les imatges són eliminades de registres públics
- Els tags són reanomenats o deprecated

**Solució ràpida abans de fer build:**

```bash
# Veure quines imatges s'usen
grep -h "^FROM " Dockerfile* | sort -u

# Si hi ha errors "not found", actualitzar versió i reintentar
docker compose build --no-cache
```

**Versions conegudes com a estables (Gen 2026):**
- `nvcr.io/nvidia/pytorch:24.12-py3` ✅
- `ollama/ollama:0.2.1` ✅
- `qdrant/qdrant:v1.9.2` ✅
- `python:3.11-slim` (per a LibreTranslate, via pip) ✅
- `erikvl87/languagetool:6.4` ✅

**Versions problemàtiques:**
- `nvcr.io/nvidia/pytorch:25.01-py3` ❌ NO EXISTEIX (versió futura)
- `libretranslate/libretranslate:1.6.1` ❌ NO TROBADA
- `libretranslate/libretranslate:1.5.0` ❌ NO TROBADA (imatge oficial eliminada)

**Solució implementada per a LibreTranslate:**
- Canvi a `python:3.11-slim` + `pip install libretranslate`
- Més confiable i es manté automàticament
- Vegeu [docs/LIBRETRANSLATE_TROUBLESHOOTING.md](../docs/LIBRETRANSLATE_TROUBLESHOOTING.md)

**Si trobes l'error "failed to resolve source metadata":**
```bash
# 1. Verificar versió disponible a Docker Hub
# Exemple per a imatges: https://hub.docker.com/r/nom/imatge/tags

# 2. Actualitzar Dockerfile (si s'aplica)
sed -i 's/VERSIO_VELLA/VERSIO_NOVA/g' Dockerfile.servei

# 3. Reconstruir
docker compose build --no-cache [servei]
```

---

## Notes per a GitHub Copilot

- **SEMPRE construir abans d'iniciar** serveis amb imatges `local/*`
- **Els perfils són excloents**: usa `gpu-nvidia` O `cpu`, no tots dos
- **Els secrets són fitxers**, no variables d'entorn directes
- **Els healthchecks tenen `start_period`**: esperar abans de diagnosticar fallades
- **Els volums amb nom** persisteixen entre reinicis, els **bind mounts** reflecteixen canvis immediats
- **Versions d'imatges**: Utilitzar sempre versions LTS/estables, no futures
- **LibreTranslate**: Usa Python + pip en lloc de la imatge Docker oficial (més confiable)
