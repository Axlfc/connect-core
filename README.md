# cognito-stack 🚀
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/README.zh-cn.md)


[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-3.8+-2496ED?logo=docker)](https://docs.docker.com/compose/)
[![n8n](https://img.shields.io/badge/n8n-1.121.0-red)](https://n8n.io/)
[![Status](https://img.shields.io/badge/Status-Activo-brightgreen)](https://github.com/Axlfc/connect-core)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js)](https://nodejs.org/)

**cognito-stack** es una plataforma modular de orquestación de IA containerizada que integra automatización de workflows, generación de imágenes e inteligencia artificial local en un único stack Docker Compose reproducible y escalable. Soporta múltiples runtimes de contenedores (Docker y Podman) y perfiles de hardware (CPU, NVIDIA GPU, AMD GPU).

> ⚠️ **Advertencia de Seguridad:** Este proyecto se encuentra en desarrollo activo y no debe ser desplegado en un entorno de producción sin una auditoría de seguridad exhaustiva.

## 📋 Tabla de contenidos

- [Descripción](#descripción)
- [Características principales](#-características-principales)
- [Problema que resuelve](#-problema-que-resuelve)
- [Casos de uso](#-casos-de-uso)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Requisitos previos](#-requisitos-previos)
- [Instalación de Docker](#-instalación-de-docker)
- [Runtimes de contenedores](#-runtimes-de-contenedores) ⭐ **Nuevo: Soporte Podman**
- [Matriz de Compatibilidad Multi-Arquitectura](#-matriz-de-compatibilidad-multi-arquitectura) ⭐ **Nuevo: Apple Silicon**
- [Instalación del proyecto](#-instalación-del-proyecto)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [Voice Services](#-voice-services)
- [Arquitectura](#-arquitectura)
- [Tecnologías utilizadas](#-tecnologías-utilizadas)
- [API y puntos de integración](#-api-y-puntos-de-integración)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Solución de problemas](#-solución-de-problemas)
- [Contribución](#-contribución)
- [Licencia](#-licencia)
- [Contacto](#-contacto)

---

## Descripción

**cognito-stack** es una solución empresarial para orquestar pipelines de inteligencia artificial y automatización sin depender de APIs externas pagadas ni perder control de los datos. Combina herramientas de código abierto líderes en la industria en una arquitectura containerizada altamente personalizable que puede ejecutarse en cualquier máquina con Docker.

La plataforma está diseñada para desarrolladores, científicos de datos y equipos de IA que necesitan:
- **Reproducibilidad**: Entorno idéntico en cualquier máquina
- **Privacidad**: Modelos y datos permanecen locales
- **Escalabilidad**: Arquitectura modular con runners externos
- **Flexibilidad**: Integración de componentes heterogéneos

---

## 🔄 Variantes

- [**simplified-stack**](simplified-stack/README.md): Versión ligera optimizada para desarrollo local que integra Drupal, Obsidian y Forgejo para flujos de trabajo de IA aislados.
- [**very-simplified-stack**](very-simplified-stack/README.md): Versión minimalista que elimina la orquestación de n8n y se centra en servicios de voz y el API de agente Cognito, diseñada para conectar con una instancia de Ollama externa.

---

## ✨ Características principales

- **Automatización de workflows** con n8n (port 5678)
  - Interfaz visual para crear workflows complejos
  - Sistema de task runners externos (JavaScript + Python)
  - Ejecución aislada de código personalizado

- **LLMs locales** con Ollama (port 11434)
  - Soporte para CPU y GPU (NVIDIA/AMD)
  - Modelos pre-cargados: Llama 3.2, Qwen, Deepseek-R1, etc.
  - Sin dependencias de APIs externas

- **Generación de imágenes** con ComfyUI (port 8188)
  - Stable Diffusion integrado
  - Soporte GPU NVIDIA optimizado
  - Procesamiento en lote de imágenes

- **Colaboración y mensajería** con Matrix Synapse (port 8008)
  - Servidor de chat federado
  - Base de datos PostgreSQL dedicada
  - Integración con Redis para sesiones

- **Vector database** con Qdrant (port 6333)
  - Almacenamiento de embeddings
  - Búsqueda semántica para RAG
  - Persistencia de datos

- **Acceso seguro remoto** con Zrok
  - Tunelización segura de webhooks
  - URLs públicas para n8n
  - Sin exponer puertos en internet

---

## 🛡️ Seguridad

El stack incluye protección contra ataques de fuerza bruta y DoS mediante **Fail2ban**.

- **Servicios Protegidos:** n8n, Forgejo, Matrix Synapse.
- **Mecanismo:** Monitoriza logs en tiempo real y bloquea IPs maliciosas que muestran comportamiento sospechoso (ej. múltiples intentos de login fallidos).
- **Configuración:** Las reglas se encuentran en el directorio `fail2ban/`. Por defecto, una IP es bloqueada por una hora tras 5 intentos fallidos.

Este sistema reduce significativamente el riesgo de accesos no autorizados y sobrecarga de servicios.

## 🎯 Problema que resuelve

**Challenge:** Integrar múltiples herramientas AI/ML en un entorno containerizado, aislado y reproducible sin:
- Gestionar múltiples servidores
- Depender de APIs externas pagadas
- Perder control de los datos
- Luchar con compatibilidades entre bibliotecas

**Solución:** cognito-stack proporciona una **arquitectura modular y cohesiva** donde:
1. **n8n** orquesta flujos de trabajo
2. **Runners externos** ejecutan código aislado (Python/JavaScript)
3. **Ollama** proporciona LLMs locales
4. **ComfyUI** genera imágenes
5. Todos los servicios se comunican vía **Docker network** sin exponerse al host

---

## � Casos de uso

### 1. **Automatización de documentación**
```
Workflow: Extraer contenido de web → Procesar con LLM → Generar resumen → Guardar en BD
Servicios: n8n + Ollama + Qdrant + PostgreSQL
```
**Ejemplo:** Monitorear blogs de noticias, extraer artículos, generar resúmenes automáticos con Llama 3.2, guardar en vector DB para búsqueda semántica.

### 2. **Generación de contenido visual**
```
Workflow: Recibir solicitud de imagen → Generar con SD3 → Procesar con filtros → Entregar
Servicios: n8n + ComfyUI + Almacenamiento compartido
```
**Ejemplo:** API endpoint que recibe descripción de imagen, genera con Stable Diffusion 3, aplica post-procesamiento con ComfyUI, retorna imagen procesada.

### 3. **Análisis de sentimientos en tiempo real**
```
Workflow: Monitorear webhook → Clasificar con LLM → Almacenar en Qdrant → Consultar con RAG
Servicios: n8n runners (Python) + Ollama + Qdrant
```
**Ejemplo:** Recibir tweets/comentarios, clasificar sentimientos con modelo cuantizado, mantener histórico en vector DB para análisis agregado.

### 4. **Pipeline de ETL con enriquecimiento AI**
```
Workflow: Extraer datos → Validar → Enriquecer con LLM → Transformar → Cargar
Servicios: n8n + Python runners + PostgreSQL + Redis
```
**Ejemplo:** Importar datos CSV, validar con reglas, usar LLM para categorización inteligente, cargar en PostgreSQL con caché en Redis.

### 5. **Sistema de recomendación local**
```
Workflow: Ingestar productos → Generar embeddings → Almacenar en Qdrant → Consultar vía API
Servicios: n8n + Ollama (embedding model) + Qdrant + Redis
```
**Ejemplo:** Catálogo de e-commerce, generar embeddings de descripciones con Ollama, buscar similares vía Qdrant, servir recomendaciones sin depender de APIs externas.

### 6. **Generación automática de reportes**
```
Workflow: Extraer KPIs → Generar gráficos → Redactar resumen → Enviar por email/Slack
Servicios: n8n + Ollama + ComfyUI (generación de imágenes de gráficos) + Matrix
```
**Ejemplo:** Diariamente extraer métricas, crear gráficos con ComfyUI, redactar análisis con Deepseek-R1, notificar vía Matrix/Slack.

### 7. **Chatbot corporativo con RAG**
```
Workflow: Cargar documentos → Generar embeddings → Almacenar → Responder consultas con contexto
Servicios: n8n + Ollama + Qdrant + Matrix Synapse
```
**Ejemplo:** Chatbot interno en Matrix Synapse que consulta documentación corporativa, usa Ollama para generar respuestas contextualizadas recuperadas de Qdrant.

### 8. **Validación y enriquecimiento de datos**
```
Workflow: Recibir input → Validar con LLM → Generar sugerencias → Solicitar confirmación
Servicios: n8n (JavaScript runners) + Ollama + PostgreSQL
```
**Ejemplo:** Formulario de contacto, validar datos con LLM (detección de spam/anomalías), generar respuesta sugerida, guardar en BD con trazabilidad.

### 9. **Procesamiento de imágenes en lote**
```
Workflow: Cargar imágenes → Procesarlas con ComfyUI → Aplicar filtros → Guardar resultados
Servicios: ComfyUI + n8n + almacenamiento compartido
```
**Ejemplo:** Carpeta con 100 imágenes, aplicar automáticamente filtros Stable Diffusion, upscaling, conversión de formato, comprensión de espacio.

### 10. **Colaboración distribuida con IA**
```
Workflow: Equipo remoto → Matrix Synapse (chat) → n8n (procesa solicitudes) → Ollama (genera insights)
Servicios: Matrix + n8n + Ollama + PostgreSQL
```
**Ejemplo:** Equipo remoto colabora en Matrix, menciona @bot-ai para análisis, bot procesa con Ollama/runners, publica resultados en canal.

---

## �📁 Estructura del proyecto

```
cognito-stack/
├── docker-compose.yml           # Definición de servicios
├── Dockerfile.n8n              # n8n con socat bridge
├── Dockerfile.runners          # Task runners (Python/JS)
├── Dockerfile.comfyui          # ComfyUI con PyTorch nightly
├── Dockerfile.matrix           # Matrix Synapse configurado
├── .env.example                # Template de variables de entorno
├── n8n-entrypoint.sh           # Script de arranque de n8n
├── n8n-task-runners.json       # Configuración de runners
├── start.sh                    # Script de inicio orquestado
├── stop.sh                     # Script de parada
├── uninitialize_env.sh         # Script de reset completo
├── update-zrok-url.sh          # Actualizar URL de tunelización
├── .github/
│   └── copilot-instructions.md # Instrucciones para agentes IA
├── shared/                     # Volumen compartido (entrada/salida)
├── models/                     # Modelos de ComfyUI
├── data/
│   └── knowledge_base/         # Base de conocimiento opcional
├── workspace/                  # Datos de ComfyUI
└── config/
    └── comfyui_plugins/        # Custom nodes de ComfyUI
```

### Directorios principales

| Directorio | Propósito | Persistencia |
|-----------|----------|--------------|
| `shared/` | Input/output de workflows y ComfyUI | Bind mount |
| `models/` | Modelos Stable Diffusion y custom nodes | Bind mount |
| `data/knowledge_base/` | Documentos para RAG (opcional) | Bind mount |
| `n8n_storage/` (volumen) | Base de datos y credenciales de n8n | Docker volume |
| `postgres_storage/` (volumen) | Base de datos PostgreSQL | Docker volume |
| `qdrant_storage/` (volumen) | Vector database | Docker volume |
| `ollama_storage/` (volumen) | Modelos de Ollama | Docker volume |
| `.zrok/` | Configuración de tunelización | Bind mount |

---

## 📦 Requisitos previos

### Software

- **Docker Engine** ≥ 20.10
  ```bash
  docker --version
  ```
- **Docker Compose** ≥ 1.29 (incluido en Desktop)
  ```bash
  docker compose version
  ```
- **Bash** 4.0+ (para scripts de inicio)
- **OpenSSL** (para generar claves de encriptación)
- **Git** (para clonar repositorio)

### Hardware

| Componente | Mínimo | Recomendado |
|-----------|--------|------------|
| **CPU** | 4 cores | 8+ cores |
| **RAM** | 8 GB | 16+ GB |
| **Almacenamiento** | 50 GB | 100+ GB |
| **GPU** (opcional) | - | NVIDIA RTX 3060+ / AMD equivalente |

### Requisitos del sistema operativo

- **Linux** (Ubuntu 20.04+ recomendado)
- **macOS** (12+) con Docker Desktop
- **Windows** con WSL 2 + Docker Desktop

### Dependencias externas (opcionales)

- **NVIDIA drivers** (si usas `--gpu-nvidia`)
- **AMD ROCm** (si usas `--gpu-amd`)
- **Zrok account** (para tunelización segura)

---

## 🎙️ Voice Services

For detailed information on the integrated voice services, please see the [Voice Services Documentation](docs/VOICE_SERVICES.md).

**Troubleshooting Whisper STT?** If you encounter issues with the speech-to-text service, check:
- [Whisper Quick Fix Guide](WHISPER_QUICKFIX.md) - Quick solutions for common issues
- [Whisper Troubleshooting](docs/WHISPER_TROUBLESHOOTING.md) - Detailed documentation

---

## � Instalación de Docker

Docker es necesario para ejecutar cognito-stack. Selecciona tu sistema operativo:

### GNU/Linux (Ubuntu/Debian)

**Paso 1: Eliminar versiones antiguas**
```bash
sudo apt-get remove docker docker.io containerd runc
```

**Paso 2: Instalar dependencias**
```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release
```

**Paso 3: Agregar repositorio oficial de Docker**
```bash
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

**Paso 4: Instalar Docker Engine**
```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verificar instalación
docker --version
docker compose version
```

**Paso 5: Agregar tu usuario al grupo docker** (evita usar `sudo`)
```bash
sudo usermod -aG docker $USER
newgrp docker

# Verificar sin sudo
docker ps
```

**Paso 6: Configurar inicio automático** (opcional)
```bash
sudo systemctl enable docker
sudo systemctl enable containerd
```

### macOS (Intel & Apple Silicon)

**Opción 1: Instalación directa (recomendado)**

1. Descargar [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Abrir el archivo `.dmg` descargado
3. Arrastra Docker.app a `/Applications`
4. Abre Docker desde Launchpad
5. Completa el proceso de instalación

**Opción 2: Usando Homebrew**
```bash
# Instalar Docker Desktop vía Homebrew
brew install --cask docker

# Verificar instalación
docker --version
docker compose version
```

**Configuración posterior**

```bash
# Docker debe estar ejecutándose (abre desde Launchpad o Spotlight)

# Completar setup
docker run hello-world  # Descarga primera imagen

# Asignar suficientes recursos en Preferences:
# - Recursos: 4+ CPU, 8+ GB RAM
# - Disk image: 100+ GB disponibles
```

#### Soporte Multi-Arquitectura: Apple Silicon & ARM64

**Para Apple Silicon (M1/M2/M3/M4) y sistemas ARM64 Linux:**

Docker Desktop/Engine detecta automáticamente tu arquitectura, pero **cognito-stack ofrece soporte optimizado**:

**Usando perfil `--arm64` (Recomendado para Apple Silicon):**
```bash
./start.sh --arm64
# O manualmente: docker compose --profile arm64 up -d
```

Este perfil selecciona automáticamente:
- ✅ **Ollama multi-arch** (soporte nativo excelente para ARM64)
- ✅ **n8n, PostgreSQL, Redis, Qdrant** (imágenes multi-arch nativas)
- ✅ **Matrix Synapse, Forgejo, Duplicati** (soporte completo)
- ⚠️ **LibreTranslate** (requiere verificación de plataforma)
- ❌ **ComfyUI** (generación de imágenes GPU - no soporta ARM64)
- ❌ **Whisper/Kokoro TTS GPU** (usan CUDA - no disponible en ARM64)

**Imágenes con soporte multi-arch nativo:**

| Servicio | Arquitecturas | Nota |
|----------|---------------|------|
| **Ollama** | amd64, arm64, darwin/* | ✅ Excelente soporte nativo en Apple Silicon |
| **n8n 1.121.0+** | amd64, arm64, arm/v7 | ✅ Manifests multi-arch completos |
| **PostgreSQL/Redis** | amd64, arm64, s390x, ppc64le | ✅ Imagen oficial multi-arch |
| **Qdrant** | amd64, arm64 | ✅ Multi-arch desde v1.0+ |
| **Matrix Synapse** | amd64, arm64 | ✅ Imagen base multi-arch |
| **Forgejo** | amd64, arm64, arm/v7, ppc64le | ✅ Imagen oficial multi-arch |

**Imágenes sin soporte ARM64 (requieren emulación lenta):**

| Servicio | Alternativa en ARM64 |
|----------|---------------------|
| **ComfyUI** | Usar en macOS Intel o GPU NVIDIA Linux |
| **Whisper-Blackwell** | Desactivar (usa CUDA) |
| **Kokoro TTS GPU** | Usar `kokoro-fastapi-cpu` (variante CPU, más lento) |
| **LibreTranslate** | Usar con `docker run --platform linux/arm64` (verificar) |

**Rendimiento esperado en Apple Silicon:**
- **Ollama LLMs**: Excelente (Apple Neural Engine acelerado)
- **n8n/workflows**: Excelente (CPU ARM64 moderno es rápido)
- **Búsquedas vectoriales (Qdrant)**: Bueno (ARM64 soporta SIMD)
- **Bases de datos**: Excelente (nativas ARM64)
- **Emulación de servicios x86**: Lento (Rosetta 2, ~1.5-3x más lento)

**Recomendación:**
- **MacBook M1/M2/M3/M4**: Usa `./start.sh --arm64` para máximo rendimiento
- Desactiva ComfyUI y servicios GPU si no los necesitas
- Ollama funcionará **nativamente rápido** en tu Mac

### Windows (WSL 2)

**Requisitos previos:**
- Windows 10/11 Pro, Enterprise o Education
- WSL 2 habilitado

**Paso 1: Habilitar WSL 2**
```powershell
# Abre PowerShell como administrador

# Habilitar Hyper-V
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Habilitar WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Reiniciar la computadora
Restart-Computer
```

**Paso 2: Actualizar kernel de WSL 2**
```powershell
wsl --update
```

**Paso 3: Instalar distribución Linux**
```powershell
# Ver distribuciones disponibles
wsl --list --online

# Instalar Ubuntu 22.04 LTS (recomendado)
wsl --install -d Ubuntu-22.04

# Establecer como predeterminada
wsl --set-default Ubuntu-22.04

# Establecer versión 2
wsl --set-version Ubuntu-22.04 2
```

**Paso 4: Instalar Docker Desktop**

1. Descargar [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. Ejecutar instalador `.exe`
3. Completar wizard de instalación
4. Reiniciar computadora si se solicita

**Paso 5: Configurar Docker para WSL 2**

En Docker Desktop:
1. Abre **Settings** → **Resources** → **WSL Integration**
2. Habilita "Enable integration with my default WSL distro"
3. Habilita "Ubuntu-22.04" si está disponible
4. Click **Apply & Restart**

**Paso 6: Verificar en WSL 2**
```bash
# En PowerShell o Windows Terminal
wsl

# Ahora en terminal Ubuntu
docker --version
docker compose version
docker run hello-world
```

**Optimización de performance**

En `%USERPROFILE%/.wslconfig` (crear si no existe):
```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
localhostForwarding=true

[interop]
enabled=true
appendWindowsPath=true
```

Luego:
```powershell
# Reiniciar WSL
wsl --shutdown
wsl
```

---

## � Runtimes de contenedores

**cognito-stack** soporta múltiples runtimes de contenedores para máxima flexibilidad. Puedes elegir entre Docker (daemon) o Podman (daemonless, más seguro).

### Comparación: Docker vs Podman

| Característica | Docker | Podman |
|---|---|---|
| **Arquitectura** | Daemon centralizado | Daemonless (sin servicio) |
| **Seguridad** | Requiere permisos root | Soporta modo rootless nativo |
| **Privilegios** | Todos los contenedores como root | Aislamiento por usuario |
| **Compatibilidad** | Estándar de facto | 100% compatible con Docker |
| **Instalación** | Docker Desktop (pesado) | Lightweight |
| **Uso en CI/CD** | Amplio soporte | Creciente |

**Recomendación**: Usa **Podman en modo rootless** para máxima seguridad en desarrollo local.

### Instalación de Podman

#### GNU/Linux (Ubuntu/Debian)

```bash
# Actualizar repositorios
sudo apt update
sudo apt upgrade -y

# Instalar Podman y Podman Compose
sudo apt install -y podman podman-compose

# Verificar instalación
podman --version
podman-compose --version
```

#### Fedora/RHEL/CentOS

```bash
# Instalar Podman (ya incluido)
sudo dnf install -y podman podman-compose

# Verificar
podman --version
podman-compose --version
```

#### Arch Linux

```bash
# Instalar
sudo pacman -S podman podman-compose

# Verificar
podman --version
podman-compose --version
```

#### macOS

```bash
# Instalar via Homebrew
brew install podman podman-compose

# Inicializar máquina virtual Podman (necesaria en macOS)
podman machine init
podman machine start

# Verificar
podman --version
podman-compose --version
```

### Configuración de Podman Rootless

El modo **rootless** permite ejecutar contenedores sin permisos de root, mejorando significativamente la seguridad.

#### Paso 1: Habilitar usuario no-root

```bash
# Configurar subuid/subgid (ejecutar como usuario regular)
# Debian/Ubuntu
sudo usermod --add-subuids 100000-165536 $USER
sudo usermod --add-subgids 100000-165536 $USER

# Fedora/RHEL
# (suele venir preconfigurado)

# Verificar configuración
grep $USER /etc/subuid
grep $USER /etc/subgid
```

#### Paso 2: Habilitar linger (persistencia de sesión)

```bash
# Permite que contenedores sigan ejecutándose tras logout
loginctl enable-linger $USER
loginctl show-user $USER | grep Linger
```

#### Paso 3: Iniciar el socket de Podman

```bash
# Habilitar socket para acceso sin sudo
systemctl --user enable podman.socket
systemctl --user start podman.socket

# Verificar
podman info | grep -i rootless
# Debería mostrar: "rootless": true
```

#### Paso 4: Configurar permisos de red (puertos < 1024)

Si necesitas mapear puertos menores a 1024 (ej: 80, 443), configura:

```bash
# Permitir al usuario asignar puertos bajos
echo "$USER:80:1" | sudo tee -a /etc/sysctl.conf
echo "$USER:443:1" | sudo tee -a /etc/sysctl.conf

# Aplicar cambios
sudo sysctl -p

# Alternativa: usar puertos > 1024 (recomendado)
# En .env: N8N_PORT=8678 (en lugar de 5678)
```

### Uso de Podman Compose

Una vez instalado, todos los comandos son idénticos a Docker Compose:

```bash
# Iniciar stack (CPU)
podman-compose up -d

# Con perfil GPU NVIDIA
podman-compose --profile gpu-nvidia up -d

# Ver estado
podman-compose ps

# Ver logs
podman-compose logs -f n8n

# Parar
podman-compose down

# Parar y eliminar datos
podman-compose down -v
```

### Consideraciones de Podman para cognito-stack

#### SELinux Labels

En sistemas con SELinux (Fedora, RHEL), es posible que necesites añadir labels `:Z` a los bind mounts:

```yaml
# En docker-compose.yml, modificar volúmenes:
volumes:
  - ./shared:/data/shared:Z        # Label para SELinux
  - ./models:/opt/models:Z
```

#### Permisos de volumen

Para asegurar que los contenedores pueden acceder a archivos:

```bash
# Dar permisos al usuario actual en directorios compartidos
chmod -R u+w ./shared ./models ./data

# Si aún hay problemas:
podman run --userns=keep-id -v ./shared:/data:Z <image>
```

#### GPU con Podman

**NVIDIA GPU:**
```bash
# Instalar nvidia-container-toolkit
sudo apt install nvidia-container-toolkit

# Configurar Podman para NVIDIA
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Usar en compose:
podman-compose --profile gpu-nvidia up -d
```

**AMD GPU:**
```bash
# Asegurar acceso a /dev/dri y /dev/kfd
sudo usermod -aG video $USER
sudo usermod -aG render $USER

# Nuevas sesiones
newgrp video
newgrp render

# Ejecutar Podman con acceso:
podman run --device /dev/dri --device /dev/kfd <image>
```

#### Networking

En modo rootless, por defecto Podman usa **slirp4netns** (más seguro pero más lento):

```bash
# Usar bridge network (más rápido, menos seguro):
podman network create demo --driver bridge
podman-compose --network demo up -d

# O cambiar en docker-compose.yml:
networks:
  demo:
    driver: bridge
    driver_opts:
      com.docker.driver.mtu: 1450
```

#### Socket de Podman

Si necesitas acceder al socket desde el host:

```bash
# Socket usuario (rootless)
export DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock

# Verificar
podman --version

# En scripts, usar:
docker-compose -H unix:///run/user/$UID/podman/podman.sock up -d
```

### Migración de Docker a Podman

Si ya usas Docker, puedes migrar a Podman:

```bash
# 1. Parar Docker
docker-compose down -v

# 2. Instalar Podman
# (ver pasos arriba según tu OS)

# 3. Copiar volúmenes Docker a Podman
# (Si es necesario - Podman puede acceder a volúmenes Docker)

# 4. Iniciar con Podman
podman-compose up -d

# 5. Verificar funcionamiento
podman-compose ps
podman-compose logs n8n
```

---

## 🏗️ Matriz de Compatibilidad Multi-Arquitectura

**cognito-stack** ofrece soporte optimizado para múltiples arquitecturas de CPU. A continuación se detalla qué componentes funcionan en cada plataforma:

### Resumen Rápido

| Plataforma | Perfil | Recomendación | Caso de uso |
|-----------|--------|---------------|-------------|
| **Intel/AMD x86-64** | `gpu-nvidia` (default) | ✅ **Recomendado** | Servidores Linux, Windows, Mac Intel |
| **Intel/AMD x86-64** | `--cpu` | ✅ | Sin GPU disponible |
| **Intel/AMD x86-64** | `--gpu-amd` | ✅ | GPU AMD Radeon |
| **Apple M1/M2/M3/M4** | `--arm64` ⭐ **NUEVO** | ✅ **Recomendado** | MacBooks Apple Silicon (nativo rápido) |
| **ARM64 Linux** | `--arm64` | ✅ | Servidores ARM64, Raspberry Pi 4+ |

### Matriz de Servicios por Arquitectura

```
┌─────────────────────────────┬───────────┬───────────┬───────────┬──────────┐
│ Servicio/Componente         │ x86-64    │ arm64     │ Apple Si  │ Notas    │
├─────────────────────────────┼───────────┼───────────┼───────────┼──────────┤
│ n8n + Task Runners          │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │          │
│ Ollama LLM Inference        │ ✅ Nativo │ ✅ Nativo │ ✅ Óptimo │ Neural   │
│ PostgreSQL + Redis          │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │          │
│ Qdrant Vector Database      │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │          │
│ Matrix Synapse (Chat)       │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │          │
│ Forgejo (Git)               │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │          │
│ LibreTranslate              │ ✅ Nativo │ ⚠️ Verif. │ ⚠️ Verif. │ CPU      │
│                             │           │           │           │          │
│ ComfyUI (Image Gen GPU)     │ ✅ NVIDIA │ ❌ No     │ ❌ No     │ GPU x86  │
│ Whisper TTS (GPU/CUDA)      │ ✅ NVIDIA │ ❌ No     │ ❌ No     │ GPU x86  │
│ Kokoro TTS (GPU/CUDA)       │ ✅ NVIDIA │ ❌ No     │ ❌ No     │ GPU x86  │
│                             │           │           │           │          │
│ Whisper TTS (CPU)           │ ✅ CPU    │ ✅ CPU    │ ✅ CPU    │ Lento    │
│ Kokoro TTS (CPU remsky)     │ ✅ CPU    │ ✅ CPU    │ ✅ CPU    │ Lento    │
│ Duplicati (Backups)         │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │          │
│ LanguageTool (Grammar)      │ ✅ Nativo │ ✅ Nativo │ ✅ Nativo │ Java     │
└─────────────────────────────┴───────────┴───────────┴───────────┴──────────┘

LEYENDA:
  ✅ Nativo  = Imagen docker multi-arch, rendimiento excelente
  ✅ Óptimo  = Rendimiento especialmente bueno en esa plataforma
  ⚠️ Verif.  = Funciona pero requiere verificación
  ❌ No      = No soportado en esa arquitectura
```

### Detalles por Arquitectura

#### **1. Intel/AMD x86-64 (Linux/Windows/macOS Intel)**

**Perfil recomendado:** `./start.sh` (defecto: GPU NVIDIA)

**Características:**
- ✅ Todos los componentes funcionan
- ✅ GPU NVIDIA (NVIDIA Docker Runtime)
- ✅ GPU AMD (ROCm)
- ✅ Servicios GPU completos (ComfyUI, Whisper/Kokoro GPU)

**Casos de uso:**
- Servidores cloud (AWS, GCP, Azure con GPU)
- Workstations Linux/Windows con GPU NVIDIA/AMD
- Macs Intel pre-2021

---

#### **2. ARM64 Linux (Servidores ARM, Raspberry Pi 4+)**

**Perfil recomendado:** `./start.sh --arm64`

**Características:**
- ✅ Todos los servicios principales funcionan nativamente
- ✅ Ollama soporta ARM64 (aunque más lento que x86-64)
- ❌ Sin GPU NVIDIA/AMD (no hay drivers para ARM)
- ❌ ComfyUI, Whisper GPU, Kokoro GPU no disponibles

**Casos de uso:**
- Servidores ARM especializados
- Raspberry Pi 4 (4GB RAM mínimo, 8GB recomendado)

**Limitaciones:**
- Ollama: ~2-5x más lento que x86-64
- Modelos grandes requieren más swap/VRAM

---

#### **3. Apple Silicon (M1/M2/M3/M4 MacBook)** ⭐ **ÓPTIMO PARA MACS**

**Perfil recomendado:** `./start.sh --arm64` (o `--apple-silicon`)

**Características:**
- ✅ Todas las imágenes son ARM64 nativas (sin emulación Rosetta 2)
- ✅ **Ollama auto-detecta Apple Neural Engine** → aceleración ML excelente
- ✅ Rendimiento LLM **superior a CPU x86-64**
- ✅ Consumo de batería y energía muy eficiente
- ❌ ComfyUI Stable Diffusion no disponible (requiere GPU x86-64)

**Ventajas sobre Mac Intel:**
- Código nativo ARM64 (sin emulación)
- Apple Neural Engine para ML: ~15-40 tokens/seg (vs 5-20 en CPU x86)
- Mejor batería en portátiles

**Limitaciones:**
- ComfyUI no soporta macOS ARM64 → Usar otra máquina para generación de imágenes
- O: delegar generación a máquina remota / servicios cloud

**Configuración recomendada:**

```bash
# Instalación completa
./start.sh --arm64

# Mínimo (sin servicios opcionales)
docker compose --profile arm64 up -d
```

---

### Matriz de Rendimiento

#### **Inferencia LLM (Ollama)**

| Plataforma | Velocidad | Notas |
|-----------|-----------|-------|
| NVIDIA GPU (x86-64) | ⚡ Muy rápido | RTX 3060+: ~100+ tokens/seg |
| AMD ROCM GPU | ⚡ Muy rápido | Similar a NVIDIA |
| Intel x86-64 CPU | 🟡 Lento | ~5-20 tokens/seg (modelo 7B) |
| ARM64 Linux CPU | 🔴 Muy lento | ~1-5 tokens/seg |
| **Apple Silicon (Native)** | ⚡⚡ **Excelente** | Neural Engine: ~15-40 tokens/seg |

**Conclusión:** En un MacBook M1+, Ollama con Apple Silicon **supera ampliamente** a CPU x86-64.

#### **Generación de Imágenes (ComfyUI)**

| Plataforma | Disponible | Rendimiento |
|-----------|-----------|-----------|
| NVIDIA GPU | ✅ | ⚡ Segundos/imagen |
| AMD ROCM GPU | ✅ | ⚡ Segundos/imagen |
| x86-64 CPU | ✅ | 🔴 Minutos/imagen |
| **Apple Silicon** | ❌ NO | Usar alternativa |

**Alternativas para Apple Silicon:**
- Ejecutar ComfyUI en máquina Linux remota
- Usar servicios cloud (Replicate, Fal.ai, RunPod)
- Integrar via API remota dentro de workflows n8n

---

## 🚀 Instalación del proyecto

## �🚀 Instalación del proyecto

### 1. Clonar el repositorio

```bash
git clone https://github.com/Axlfc/connect-core.git
cd cognito-stack
```

### 2. Configurar variables de entorno

```bash
# Copiar template de configuración
cp .env.example .env

# Generar claves seguras de encriptación
openssl rand -base64 32 > /tmp/key1.txt
openssl rand -base64 32 > /tmp/key2.txt
openssl rand -base64 32 > /tmp/key3.txt

# Editar .env y reemplazar valores críticos
nano .env
```

**Variables críticas a configurar en `.env`:**

```env
# 🔐 Seguridad - Generar con: openssl rand -base64 32
N8N_ENCRYPTION_KEY=<generar_nueva>
N8N_USER_MANAGEMENT_JWT_SECRET=<generar_nueva>
N8N_AUTH_JWT_SECRET=<generar_nueva>
N8N_RUNNERS_AUTH_TOKEN=<generar_nueva>

# 🔐 Bases de datos
POSTGRES_PASSWORD=<cambiar_contraseña_segura>
REDIS_PASSWORD=<cambiar_contraseña_segura>

# 🌐 Acceso remoto (opcional - para Zrok)
ZROK_AUTH_TOKEN=<tu_token_zrok>
ZROK_API_ENDPOINT=https://api.zrok.io
WEBHOOK_URL=https://tu-nombre-unico.share.zrok.io
```

### 3. Preparar Permisos de Directorios (¡Paso Crítico!)

Antes de iniciar el stack por primera vez, es necesario configurar los permisos correctos para los directorios de logs que serán montados dentro de los contenedores. Esto previene errores de "permission denied" en servicios como PostgreSQL y Redis, que se ejecutan como usuarios no-root.

El script `setup-permissions.sh` se encarga de:
1. Crear todos los directorios de logs en `./logs`.
2. Asignar la propiedad correcta (`chown`) a los directorios de logs para PostgreSQL y Redis.

**Ejecuta el siguiente comando:**
```bash
# Es necesario usar sudo porque cambia la propiedad de los directorios
sudo ./setup-permissions.sh
```
Este script solo necesita ejecutarse una vez, antes del primer inicio.

### 4. Iniciar el stack

```bash
# Opción 1: GPU NVIDIA (defecto)
./start.sh

# Opción 2: Solo CPU
./start.sh --cpu

# Opción 3: GPU AMD
./start.sh --gpu-amd

# Opción 4: ARM64 / Apple Silicon (M1/M2/M3/M4)
./start.sh --arm64
```

**Perfiles de Hardware Disponibles:**

| Perfil | Hardware | Descripción | Comando |
|--------|----------|-------------|---------|
| **Defecto (GPU NVIDIA)** | NVIDIA GPU | Requiere NVIDIA Docker Toolkit + GPU RTX/RTX30+ | `./start.sh` |
| **CPU** | CPU Only | Para máquinas sin GPU; todos los servicios menos ComfyUI GPU | `./start.sh --cpu` |
| **GPU AMD** | AMD ROCM GPU | GPU AMD Radeon compatibles con ROCm | `./start.sh --gpu-amd` |
| **ARM64** ⭐ **NUEVO** | Apple Silicon / ARM64 | M1/M2/M3/M4 Macs y servidores ARM64 Linux; soporte multi-arch optimizado | `./start.sh --arm64` |

**Características por perfil:**

| Servicio | NVIDIA | CPU | AMD | ARM64 |
|----------|--------|-----|-----|-------|
| n8n + runners | ✅ | ✅ | ✅ | ✅ Nativo |
| Ollama LLMs | ✅ | ✅ | ✅ | ✅ Nativo (excelente) |
| ComfyUI (img gen) | ✅ GPU | ❌ | ❌ | ❌ |
| Matrix Synapse | ✅ | ✅ | ✅ | ✅ Nativo |
| PostgreSQL/Redis | ✅ | ✅ | ✅ | ✅ Nativo |
| Whisper TTS (GPU) | ✅ GPU | ❌ | ❌ | ❌ |
| Whisper TTS (CPU) | ✅ | ✅ | ✅ | ✅ Nativo |

To run with voice services, use one of the following commands:

- **GPU**: `docker compose --profile gpu-nvidia --profile voice up -d`
- **CPU**: `docker compose --profile voice-cpu up -d`

El script ejecutará:
1. ✅ Limpieza de contenedores previos
2. ✅ Inicio de servicios en orden de dependencias
3. ✅ Espera a health checks
4. ✅ Muestra URLs de acceso

**Tiempo estimado de inicio:** 60-120 segundos

### 5. Verificar estado

```bash
# Ver estado de servicios
docker compose ps

# Ver logs en tiempo real
docker compose logs -f n8n

# Health check manual
curl http://localhost:5678/healthz
```

---

## ⚙️ Configuración

### Tabla de configuración principal

```env
# ============================================
# n8n - Orquestación de workflows
# ============================================
N8N_VERSION=latest              # Versión de n8n
N8N_PORT=5678                   # Puerto de acceso
N8N_PROTOCOL=http               # http o https
N8N_ENCRYPTION_KEY=***          # Generar: openssl rand -base64 32
N8N_USER_MANAGEMENT_JWT_SECRET=***  # Generar: openssl rand -base64 32
N8N_AUTH_JWT_SECRET=***         # Generar: openssl rand -base64 32
N8N_RUNNERS_ENABLED=true        # Habilitar task runners externos
N8N_RUNNERS_AUTH_TOKEN=***      # Token compartido runners
N8N_RUNNERS_MAX_CONCURRENCY=5   # Máximo de tareas simultáneas

# ============================================
# PostgreSQL - Base de datos principal
# ============================================
POSTGRES_PASSWORD=***           # Contraseña segura
POSTGRES_DB=n8n                 # Nombre BD
POSTGRES_PORT=5432              # Puerto (solo localhost)

# ============================================
# Redis - Cache y sesiones
# ============================================
REDIS_PASSWORD=***              # Contraseña segura
REDIS_PORT=6379                 # Puerto (solo localhost)
REDIS_MAXMEMORY=256mb           # Tamaño máximo de memoria

# ============================================
# Ollama - LLM local
# ============================================
OLLAMA_BASE_URL=http://ollama:11434  # URL interna
OLLAMA_PORT=11434               # Puerto API

# ============================================
# ComfyUI / Stable Diffusion - Generación de imágenes
# ============================================
COMFYUI_PORT=8188               # Puerto acceso
COMFYUI_GPU_DEVICE=0            # Device NVIDIA (0, 1, ...)

# ============================================
# Qdrant - Vector database
# ============================================
QDRANT_URL=http://qdrant:6333   # URL interna
QDRANT_PORT=6333                # Puerto API

# ============================================
# Matrix Synapse - Chat federado
# ============================================
SYNAPSE_SERVER_NAME=matrix.local  # Nombre del servidor
MATRIX_PORT=8008                # Puerto HTTP
MATRIX_ADMIN_USER=admin         # Usuario administrador
MATRIX_POSTGRES_PASSWORD=***    # Contraseña BD Matrix separada

# ============================================
# Zrok - Tunelización segura (opcional)
# ============================================
ZROK_AUTH_TOKEN=***             # Token de Zrok
ZROK_API_ENDPOINT=https://api.zrok.io
WEBHOOK_URL=https://nombre-unico.share.zrok.io
```

### Variables de entorno por perfil

```bash
# Perfil CPU (defecto)
./start.sh --cpu
# Usa: ollama, n8n, redis, postgres (sin comfyui GPU)

# Perfil NVIDIA GPU
./start.sh --gpu-nvidia         # o ./start.sh (defecto)
# Usa: ollama-gpu-nvidia, comfyui-gpu-nvidia, n8n, runners

# Perfil AMD GPU
./start.sh --gpu-amd
# Usa: ollama-gpu-amd, comfyui-gpu-amd, n8n, runners
```

### Ajuste de recursos

En `docker-compose.yml`, búsca `services.n8n.deploy.resources`:

```yaml
services:
  n8n:
    deploy:
      resources:
        limits:
          cpus: '2'                    # Máximo 2 CPU cores
          memory: 4G                   # Máximo 4 GB RAM
        reservations:
          cpus: '1'                    # Reservar 1 CPU
          memory: 2G                   # Reservar 2 GB
          devices:
            - driver: nvidia           # GPU NVIDIA
              count: 1
              capabilities: [gpu]
```

Edita según tu hardware disponible.

### Conectar proveedores externos (opcional)

#### Brave Search API (para workflows)
```env
MCP_BRAVE_API_KEY=your_key_here
```

#### Conexión a servicios en la red local
```bash
# Si necesitas acceder a servicios fuera de Docker:
docker network inspect demo  # Ver detalles de red

# Usar "host.docker.internal" en macOS/Windows
# Usar IP del host en Linux (ej: 192.168.x.x)
```

---

## 💻 Uso

### Acceso a interfaces

| Servicio | URL | Puerto | Descripción |
|---------|-----|--------|-----------|
| **n8n** (workflows) | http://localhost:5678 | 5678 | Orquestación de workflows y automatización |
| **ComfyUI** (imágenes) | http://localhost:8188 | 8188 | Generación de imágenes con Stable Diffusion |
| **Matrix** (chat) | http://localhost:8008 | 8008 | Servidor de chat federado |
| **Ollama** (API LLM) | http://localhost:11434 | 11434 | API de modelos de lenguaje locales |
| **Qdrant** (vector DB) | http://localhost:6333 | 6333 | Base de datos vectorial para embeddings |
| **Forgejo** (Git) | http://localhost:3002 | 3002 | Servidor Git self-hosted |
| **Authelia** (auth) | http://localhost:9091 | 9091 | Sistema de autenticación centralizado |
| **Whisper STT** (GPU) | http://localhost:9001 | 9001 | Speech-to-Text con GPU |
| **Whisper STT** (CPU) | http://localhost:9002 | 9002 | Speech-to-Text con CPU |
| **Kokoro TTS** (GPU) | http://localhost:8880 | 8880 | Text-to-Speech con GPU |
| **Kokoro TTS** (CPU) | http://localhost:8881 | 8881 | Text-to-Speech con CPU |
| **Uptime Kuma** | http://localhost:3001 | 3001 | Monitoreo de servicios |
| **Prometheus** | http://localhost:9090 | 9090 | Metrics collection (enable with `--profile monitoring`) |
| **Grafana** | https://monitoring.localhost | 3000 | Dashboarding (enable with `--profile monitoring`, protected by Authelia) |
| **Uptime Kuma** | https://status.localhost | 3001 | Monitoreo de servicios (protected by Authelia) |
| **LibreTranslate** | http://localhost:5000 | 5000 | Traducción automática (190+ idiomas) |

> Nota: `cAdvisor` necesita acceso al sistema de ficheros y sockets del host para recoger métricas de contenedores. Esto puede exponer información del host; se recomienda no publicar su puerto en producción y usarlo sólo para debugging local tras evaluar el riesgo.
| **LanguageTool** | http://localhost:8010 | 8010 | Corrección gramatical |
| **PostgreSQL** | localhost:5432 | 5432 | Base de datos principal (n8n, Matrix, Forgejo) |
| **Redis** | localhost:6379 | 6379 | Cache y sesiones |

### Resolución DNS local (Opcional)

Para facilitar el acceso a los servicios, puedes asignar nombres de dominio locales y usarlos en lugar de 'localhost' o '127.0.0.1'. Esto te permite acceder a servicios como `http://n8n.local:5678` o `http://forgejo.local:3002` directamente desde tu navegador, lo cual es más conveniente.

Para ello, debes editar el archivo `hosts` de tu sistema y añadir la siguiente línea:

```
127.0.0.1 n8n.localhost ollama.localhost comfyui.localhost matrix.localhost voice-gateway.localhost forgejo.localhost libretranslate.localhost languagetool.localhost status.localhost duplicati.localhost auth.localhost
```

**Instrucciones por sistema operativo:**

**Linux y macOS:**

1.  Abre una terminal.
2.  Ejecuta el siguiente comando para editar el archivo con `nano` (puedes usar `vim` o tu editor preferido):
    ```bash
    sudo nano /etc/hosts
    ```
3.  Añade la línea al final del archivo.
4.  Guarda los cambios (en `nano`, `Ctrl+O`, `Enter`, y luego `Ctrl+X`).

**Windows:**

1.  Abre el Bloc de notas (`Notepad`) como Administrador.
    -   Busca "Bloc de notas" en el menú de inicio, haz clic derecho y selecciona "Ejecutar como administrador".
2.  En el Bloc de notas, ve a `Archivo` > `Abrir`.
3.  Navega a `C:\Windows\System32\drivers\etc`.
4.  Cambia el filtro de archivos de "Documentos de texto (*.txt)" a "Todos los archivos (*.*)".
5.  Selecciona y abre el archivo `hosts`.
6.  Añade la línea al final del archivo.
7.  Guarda los cambios.

Una vez guardado, podrás acceder a los servicios usando los dominios `.local` junto con sus respectivos puertos directamente en tu navegador.

### Ejemplos de uso

#### 1. Crear un workflow en n8n

```
1. Abrir http://localhost:5678
2. Crear nuevo workflow
3. Agregar nodos:
   - Start node
   - HTTP Request (Ollama API)
   - Process (JavaScript/Python code)
   - Save to file
4. Ejecutar y ver resultados en ./shared/
```

#### 2. Generar imágenes con ComfyUI

```
1. Acceder a http://localhost:8188
2. Cargar workflow de Stable Diffusion
3. Especificar prompt
4. Generar - outputs en ./shared/
```

#### 3. Consultar LLM local

```bash
# Listar modelos disponibles
curl http://localhost:11434/api/tags

# Generar texto
curl http://localhost:11434/api/generate \
  -X POST \
  -d '{"model":"llama3.2", "prompt":"Explain AI in 50 words"}'
```

#### 4. Conectarse a Matrix

```
1. Cliente: Element.io o similar
2. Servidor: http://localhost:8008
3. Usuario: @admin:matrix.local
4. Crear salas para colaboración
```

### API Health Checks

Aquí tienes algunos comandos `curl` útiles para verificar que los servicios de IA principales están funcionando correctamente. Ejecútalos desde tu terminal en la máquina host.

#### 1. Ollama (Generación de Texto)

Este comando envía un prompt específico a Ollama y espera una respuesta concreta.

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "esto es una prueba, si recibiste este mensaje simplemente responde \"ALL CLEAR\"",
  "stream": false
}' | jq .response
```

**Respuesta esperada:**
Deberías ver `"ALL CLEAR"` en la salida. Si el modelo `llama3.2` no está disponible, puedes listar los modelos existentes con `curl http://localhost:11434/api/tags` y usar uno de los que aparezcan.

#### 2. Pipeline de Voz (TTS -> STT)

Este es un proceso de dos pasos para probar el flujo completo de Texto-a-Voz y Voz-a-Texto.

##### Paso A: Generar Audio desde Texto (TTS)

Este comando convierte una frase de texto en un archivo de audio llamado `test_audio.wav`.

```bash
curl -X POST "http://localhost:8880/tts" \
  -d "text=this is a test" \
  --output test_audio.wav
```

**Verificación:**
Se debería crear un archivo `test_audio.wav` en tu directorio actual. Puedes intentar reproducirlo para confirmar que contiene el audio.

##### Paso B: Transcribir Audio a Texto (STT)

Este comando envía el archivo `test_audio.wav` al servicio de transcripción y devuelve el texto reconocido.

**Para GPU (puerto 9001):**
```bash
curl -X POST -F 'audio_file=@test_audio.wav' http://localhost:9001/asr | jq .text
```

**Para CPU (puerto 9002):**
```bash
# Nota: asegúrate de haber iniciado el stack con el perfil de voz para CPU
curl -X POST -F 'audio_file=@test_audio.wav' http://localhost:9002/asr | jq .text
```

**Respuesta esperada:**
Deberías ver `"this is a test"` en la salida. Pequeñas variaciones son aceptables, pero debería ser muy similar.

### Entorno de Staging (Pruebas)

cognito-stack incluye un entorno de staging aislado para probar cambios sin afectar la configuración de producción.

**Características:**
- **Compose file separado:** `docker-compose.staging.yml`
- **Configuración aislada:** `.env.staging`
- **Volúmenes de datos separados:** `staging-n8n_storage`, `staging-postgres_storage`, etc.
- **Nombres de servicios con prefijo:** `staging-n8n`, `staging-postgres`, etc.

**Uso del entorno de Staging:**

Para gestionar el entorno de staging, simplemente añade el flag `--staging` a los scripts `start.sh` y `stop.sh`.

```bash
# Iniciar el entorno de staging (solo CPU)
./start.sh --staging --cpu

# Iniciar staging con GPU NVIDIA y servicios de voz
./start.sh --staging --voice

# Parar el entorno de staging
./stop.sh --staging

# Parar y borrar TODOS los datos de staging
./stop.sh --staging --volumes
```

### Comandos disponibles

```bash
# ℹ️ Información
./start.sh --help              # Ver opciones de startup

# 🚀 Control de stack
./start.sh                     # Iniciar con GPU NVIDIA
./start.sh --cpu               # Iniciar con CPU
./start.sh --gpu-amd           # Iniciar con GPU AMD
./stop.sh                      # Parar servicios
./stop.sh --volumes            # Parar y borrar datos

# 🔧 Mantenimiento
./uninitialize_env.sh          # Reset completo (elimina .env y datos)
./update-zrok-url.sh           # Actualizar URL de tunelización

# 📊 Logs y debugging
docker compose logs n8n        # Ver logs de n8n
docker compose logs -f n8n-runner  # Logs de runners en tiempo real
docker exec -it n8n bash       # Shell dentro del contenedor

# 🔨 Rebuild (después de editar Dockerfile)
docker compose build n8n-runner
docker compose up -d n8n-runner
```

### Agregar paquetes Python

Para usar librerías adicionales en workflows de Python:

```bash
# 1. Editar Dockerfile.runners
nano Dockerfile.runners

# 2. Agregar paquete a la línea de pip install
# Ejemplo: agregar 'requests-html'
RUN /home/runner/custom-venv/bin/pip install --no-cache-dir \
    websockets pandas numpy ... requests-html

# 3. Reconstruir y reiniciar
docker compose build n8n-runner
docker compose up -d n8n-runner
```

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│           Docker Network: "demo" (bridge)               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐           ┌──────────────────┐   │
│  │   n8n (5678)     │◄─────────►│  n8n-runner      │   │
│  │  (Workflows)     │ Task      │ (Python/JS)      │   │
│  │                  │ Broker    │ (5681, 5682)     │   │
│  └────────┬─────────┘           └──────────────────┘   │
│           │                                             │
│           ├──────────┬─────────────┬──────────────┐     │
│           │          │             │              │     │
│    ┌──────▼──┐ ┌────▼────┐ ┌────▼────┐ ┌─────▼──┐    │
│    │ Ollama  │ │ComfyUI  │ │ Qdrant  │ │ Matrix │    │
│    │ (LLMs)  │ │(Images) │ │(Vectors)│ │(Chat)  │    │
│    └─────────┘ └─────────┘ └─────────┘ └────────┘    │
│                                                          │
│    ┌────────────┐  ┌────────────┐  ┌──────────────┐   │
│    │ PostgreSQL │  │   Redis    │  │    Zrok      │   │
│    │   (n8n)    │  │  (cache)   │  │ (tunneling)  │   │
│    └────────────┘  └────────────┘  └──────────────┘   │
│                                                          │
│    [matrix-postgres] - BD separada para Matrix        │
│                                                          │
└─────────────────────────────────────────────────────────┘
         ▼                  ▼                   ▼
  [Shared Storage]   [Models Storage]   [External Internet]
      ./shared/          ./models/       (via Zrok)
```

### Componentes

| Servicio | Rol | Puertos | Volúmenes |
|---------|-----|--------|----------|
| **postgres** | BD principal | 5432 | `postgres_storage` |
| **n8n** | Orquestación | 5678, 5679 | `n8n_storage` |
| **n8n-runner** | Task execution | 5681, 5682 | n8n_storage |
| **ollama** | LLMs locales | 11434 | `ollama_storage` |
| **comfyui** | Image generation | 8188 | models, shared |
| **qdrant** | Vector DB | 6333 | `qdrant_storage` |
| **redis** | Cache | 6379 | `redis_data` |
| **matrix-synapse** | Chat server | 8008, 8448 | `matrix_data` |
| **matrix-postgres** | BD Matrix | 5433 | `matrix_postgres` |
| **zrok-client** | Tunneling | - | `.zrok` |

### Flujos de datos

1. **Ejecución de workflows:**
   - n8n recibe trigger (HTTP, schedule, webhook)
   - Envía tarea a task broker
   - Runner ejecuta código aislado
   - Resultados guardados en `n8n_storage` y `./shared`

2. **Generación de imágenes:**
   - n8n envía prompt a ComfyUI
   - ComfyUI usa modelos en `./models`
   - Output en `./shared`

3. **Consultas LLM:**
   - Workflow llama a `http://ollama:11434/api/generate`
   - Ollama procesa en GPU (si disponible)
   - Respuesta en formato JSON

4. **Búsqueda semántica (RAG):**
   - Embeddings almacenados en Qdrant
   - Consultas a través de API de n8n
   - Información recuperada para contexto de LLM

---

## 🛠️ Tecnologías utilizadas

### Core Orchestration
- **n8n 1.121.0** - Workflow automation platform
- **Docker Compose 3.8+** - Container orchestration (producción)
- **Podman Compose** - Container orchestration alternativo (más seguro)

### AI/ML Stack
- **Ollama** - Local LLM inference engine (CPU/GPU support)
- **ComfyUI** - Image generation with Stable Diffusion
- **OpenAI Whisper** - Speech-to-Text (STT) con GPU support
- **Kokoro** - Text-to-Speech (TTS) con GPU support
- **PyTorch (nightly)** - Deep learning framework
- **Qdrant** - Vector database for embeddings
- **Python 3.x** - Data processing & custom logic
- **Node.js** - JavaScript task runners

### Infrastructure & Security
- **PostgreSQL 16** - Primary database (n8n, Matrix, Forgejo)
- **Redis 7.2** - Caching & sessions
- **Matrix Synapse** - Federated chat server
- **Forgejo** - Git self-hosted with MCP integration
- **Authelia 4.38.0+** - Authentication & authorization (SSO, 2FA, WebAuthn)
- **Fail2ban** - Intrusion prevention system
- **Nginx Proxy** - Reverse proxy with ACME SSL/TLS automation
- **Zrok** - Secure tunneling for webhooks
- **Uptime Kuma** - Service monitoring
- **Duplicati** - Automated backups

### Text Processing
- **LibreTranslate** - Machine translation (190+ languages)
- **LanguageTool** - Grammar and spell checking

### Models & Libraries
- **Llama 3.2** - Meta's language model
- **Qwen 2.5-Coder** - Alibaba's coding model
- **Deepseek-R1** - Reasoning model
- **Mistral** - Fast inference model
- **Nomic Embed Text** - Embeddings model
- **Stable Diffusion 3** - Image generation
- **pandas, numpy, scikit-learn, requests, beautifulsoup4, websockets** - Data science & utility stack

---

## 🔄 CI/CD Pipeline

Cognito-stack incluye un pipeline completo de CI/CD para validación automática y despliegue de cambios.

### Workflows de GitHub Actions

#### 1. **Validate & Lint** (`.github/workflows/validate.yml`)
Se ejecuta en cada push y pull request:

```
✓ YAML Validation        - Valida docker-compose.yml y JSON
✓ Shell Script Linting   - shellcheck en todos los scripts bash
✓ Dockerfile Linting     - hadolint en todos los Dockerfiles
✓ Docker Compose Validation - Verifica sintaxis y servicios
✓ Security Checks        - Busca credenciales expuestas
✓ Configuration Validation - Verifica variables de entorno
```

#### 2. **Build & Push** (`.github/workflows/build.yml`)
Se ejecuta en commits a master:

```
✓ Test Build         - Construye imágenes en PRs (no push)
✓ Build & Push       - Publica en GHCR en master
✓ Compose Validation - Verifica compatibilidad
```

### Validación local

Antes de hacer push, ejecuta las validaciones localmente:

```bash
# Validación completa (recomendado)
./scripts/validate.sh

# Smoke test (requiere Docker)
./scripts/smoke-test.sh          # CPU
./scripts/smoke-test.sh gpu-nvidia   # NVIDIA GPU
./scripts/smoke-test.sh gpu-amd      # AMD GPU
```

### Requisitos para CI/CD

**Pre-requisitos para contribuir:**
- ✅ Pasar todas las validaciones locales
- ✅ No añadir credenciales o secrets en el código
- ✅ Documentación actualizada
- ✅ Commits con mensajes claros

**Pre-requisitos para merge:**
- ✅ GitHub Actions validaciones exitosas
- ✅ Al menos 1 review aprobado
- ✅ No hay conflictos de merge

### Herramientas utilizadas en CI/CD

| Herramienta | Propósito | Instalación local |
|-----------|----------|-------------------|
| **ShellCheck** | Linting de scripts bash | `apt install shellcheck` |
| **Hadolint** | Linting de Dockerfiles | `apt install hadolint` |
| **Markdownlint** | Validación de markdown | `npm install -g markdownlint-cli` |
| **PyYAML** | Validación de YAML | `pip install pyyaml` |
| **Docker** | Validación de compose | [docker.com](https://docker.com) |

### Publicación en registry

Las imágenes se publican automáticamente en **GHCR** (GitHub Container Registry):

```bash
# Pull de imágenes publicadas
docker pull ghcr.io/axlfc/cognito-stack:n8n-latest
docker pull ghcr.io/axlfc/cognito-stack:runners-latest
docker pull ghcr.io/axlfc/cognito-stack:comfyui-latest
docker pull ghcr.io/axlfc/cognito-stack:matrix-latest
```

### Debugging de CI/CD

**Si falla GitHub Actions:**

1. **Ver logs:**
   - Ve a "Actions" en GitHub
   - Selecciona el workflow fallido
   - Ver detalles del job

2. **Validar localmente:**
   ```bash
   ./scripts/validate.sh  # Ejecuta las mismas comprobaciones
   ```

3. **Problemas comunes:**
   - **Docker Compose fail:** `docker compose config --quiet`

---

## 🔌 API y puntos de integración

### Ollama API (LLMs locales)

```bash
# Endpoint base
http://localhost:11434

# Listar modelos disponibles
curl http://localhost:11434/api/tags

# Generar texto (chat)
curl http://localhost:11434/api/generate \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "¿Cuál es la capital de Francia?",
    "stream": false
  }'

# Generar con streaming (respuesta en tiempo real)
curl http://localhost:11434/api/generate \
  -X POST \
  -d '{
    "model": "llama3.2",
    "prompt": "Escribe un poema",
    "stream": true
  }' | jq '.response'

# Crear embeddings (para RAG)
curl http://localhost:11434/api/embed \
  -X POST \
  -d '{
    "model": "nomic-embed-text",
    "input": "documento para vectorizar"
  }'
```

### Qdrant Vector DB

```bash
# Endpoint base
http://localhost:6333

# Crear colección
curl -X PUT http://localhost:6333/collections/docs \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    }
  }'

# Insertar vectores
curl -X PUT http://localhost:6333/collections/docs/points?wait=true \
  -H "Content-Type: application/json" \
  -d '{
    "points": [
      {
        "id": 1,
        "vector": [0.1, 0.2, 0.3, ...],
        "payload": {"text": "documento original"}
      }
    ]
  }'

# Buscar similares
curl -X POST http://localhost:6333/collections/docs/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, 0.3, ...],
    "limit": 5,
    "with_payload": true
  }'
```

### n8n Webhooks

```bash
# Webhook para triggers
https://tu-nombre-unico.share.zrok.io/webhook/mi-workflow

# POST con datos
curl -X POST https://tu-nombre-unico.share.zrok.io/webhook/mi-workflow \
  -H "Content-Type: application/json" \
  -d '{"nombre": "datos", "valor": 123}'

# n8n procesa y retorna resultados
```

### Matrix Synapse Client

```bash
# Endpoint base
http://localhost:8008

# Login
curl -X POST http://localhost:8008/_matrix/client/r0/login \
  -d '{
    "type": "m.login.password",
    "user": "admin",
    "password": "password"
  }'

# Enviar mensaje
curl -X POST http://localhost:8008/_matrix/client/r0/rooms/!room_id/send/m.room.message \
  -H "Authorization: Bearer access_token" \
  -d '{
    "msgtype": "m.text",
    "body": "Mensaje desde API"
  }'
```

### ComfyUI Workflow API

```bash
# Endpoint base
http://localhost:8188

# POST workflow JSON
curl -X POST http://localhost:8188/api/prompt \
  -H "Content-Type: application/json" \
  -d @workflow.json

# Respuesta incluye prompt_id
# Monitoring en WebSocket para progreso

# Outputs disponibles en ./shared/
```

### PostgreSQL Connection

```bash
# Desde host
psql -h localhost -U postgres -d n8n -p 5432

# Query ejemplo
SELECT * FROM n8n_nodes;

# Desde dentro de Docker
docker exec -it postgres psql -U postgres -d n8n
```

### Redis Connection

```bash
# Desde host
redis-cli -h localhost -p 6379 -a <REDIS_PASSWORD>

# Comandos
KEYS n8n:*
GET n8n:key
EXPIRE key 3600
```

---

## 🔧 Solución de problemas

### Problemas de arranque

#### Docker no funciona
**Síntoma:** `command not found: docker`

**Solución:**
```bash
# Verificar instalación
docker --version
docker compose version

# Si no está instalado, ver sección "Instalación de Docker"
# En Linux, verificar que estés en el grupo docker:
groups $USER
# Si no incluye "docker":
sudo usermod -aG docker $USER
newgrp docker
```

#### Error: "Cannot connect to Docker daemon"
**Síntoma:** `Cannot connect to Docker daemon at unix:///var/run/docker.sock`

**Solución:**
```bash
# En Linux
sudo systemctl start docker
sudo systemctl enable docker

# En macOS
# Abre Docker Desktop desde Launchpad/Applications

# En Windows (WSL2)
# Asegúrate que WSL Integration está habilitada en Docker Desktop Settings
```

#### Puertos ya en uso
**Síntoma:** `Error: bind: address already in use`

**Solución:**
```bash
# Encontrar proceso usando puerto (ej: 5678)
lsof -i :5678     # macOS/Linux
netstat -ano | findstr :5678  # Windows

# Detener servicio previo o usar puerto diferente
# En .env, cambiar N8N_PORT=5678 a N8N_PORT=5679
```

#### Sin espacio en disco
**Síntoma:** `no space left on device`

**Solución:**
```bash
# Ver espacio disponible
df -h

# Limpiar Docker
docker system prune -a --volumes

# Si persiste, eliminar datos de trabajo
./stop.sh --volumes  # ⚠️ Esto elimina todos los datos

# Asegurar 50+ GB disponibles
```

### Problemas de configuración

#### Variables de entorno no se aplican
**Síntoma:** Los cambios en `.env` no se reflejan

**Solución:**
```bash
# .env solo se lee al iniciar
./stop.sh
docker compose up -d
```

#### Errores de encriptación
**Síntoma:** `N8N_ENCRYPTION_KEY is invalid`

**Solución:**
```bash
# Regenerar claves
openssl rand -base64 32
# Copiar a .env
N8N_ENCRYPTION_KEY=<nuevo_valor>

# Reiniciar
./stop.sh
./start.sh
```

#### Contraseña de PostgreSQL incorrecta
**Síntoma:** `FATAL: password authentication failed`

**Solución:**
```bash
# Usar contraseña original del .env
# O regenerar (requiere reset):
./uninitialize_env.sh
cp .env.example .env
# Configurar nuevas credenciales
./start.sh
```

### Problemas de servicios

#### n8n no inicia
**Síntoma:** `curl http://localhost:5678/healthz` → Connection refused

**Solución:**
```bash
# Ver logs
docker compose logs n8n

# Problemas comunes:
# 1. Puerto ocupado → Cambiar N8N_PORT en .env
# 2. Sin espacio → docker system prune -a
# 3. BD no lista → Esperar más tiempo
./stop.sh
./start.sh
```

#### Runners no se conectan
**Síntoma:** "No runners available" en n8n, Python/JS code nodes no funcionan

**Solución:**
```bash
# Verificar token compartido
# En .env, ambas líneas deben ser iguales:
grep N8N_RUNNERS_AUTH_TOKEN .env

# Ver logs del runner
docker compose logs n8n-runner

# Reiniciar runners
docker compose restart n8n-runner

# Verificar conectividad broker
docker exec n8n-runner curl http://n8n:5679/health
```

#### Ollama no genera respuestas
**Síntoma:** `curl http://localhost:11434/api/tags` → vacío o error

**Solución:**
```bash
# Ver logs
docker compose logs ollama

# Modelos no descargados
# Ver en compose: servicios "ollama-pull-*"
docker compose logs ollama-pull-llama3.2

# Descargar modelo manualmente
docker exec ollama ollama pull llama3.2

# Esperar descarga (depende de internet y modelo)
# Luego verificar disponibilidad
curl http://localhost:11434/api/tags | jq
```

#### ComfyUI genera error en GPU
**Síntoma:** CUDA out of memory o GPU error

**Solución:**
```bash
# Verificar GPU disponible
nvidia-smi  # NVIDIA
rocm-smi    # AMD

# Reducir batch size en workflow de ComfyUI
# En ComfyUI UI, ajustar parámetros de generación

# O cambiar a CPU
./stop.sh
./start.sh --cpu
```

#### Qdrant no guarda datos
**Síntoma:** Datos perdidos después de restart

**Solución:**
```bash
# Verificar volumen existe
docker volume ls | grep qdrant

# Verificar que está montado
docker inspect cognito-stack_qdrant | grep -A 10 Mounts

# Si no existe volumen, crear:
docker volume create qdrant_storage

# Reiniciar servicio
docker compose up -d qdrant
```

### Problemas de conectividad

#### Servicios no se comunican entre sí
**Síntoma:** "Cannot reach ollama:11434" desde n8n

**Solución:**
```bash
# Verificar red Docker
docker network inspect demo

# Todos los servicios deben estar en la red "demo"
docker inspect n8n | grep Networks

# Probar conectividad dentro de Docker
docker exec n8n curl http://ollama:11434/api/tags

# Si falla, reiniciar servicios
./stop.sh
docker compose down
./start.sh
```

#### Zrok no funciona
**Síntoma:** `ZROK_AUTH_TOKEN` error o tunelización no disponible

**Solución:**
```bash
# Verificar token en .env
grep ZROK_AUTH_TOKEN .env

# Token inválido
# 1. Ir a https://zrok.io
# 2. Crear cuenta y obtener token
# 3. Actualizar en .env
# 4. Ejecutar:
./update-zrok-url.sh

# Ver URL generada
docker compose logs zrok-client
```

#### Acceso a Matrix fallido
**Síntoma:** "Cannot connect to matrix.local" o CORS error

**Solución:**
```bash
# Verificar que Matrix está activo
docker compose ps matrix-synapse

# Usar IP en lugar de hostname (si es necesario)
# En lugar de: http://matrix.local:8008
# Usa: http://localhost:8008

# Verificar health
curl http://localhost:8008/_matrix/client/versions
```

### Problemas de performance

#### Stack lento
**Síntoma:** Respuestas lentas, alto uso de CPU/RAM

**Solución:**
```bash
# Ver recursos en tiempo real
docker stats

# Reducir concurrencia de runners
# En .env:
N8N_RUNNERS_MAX_CONCURRENCY=2  # Reducir de 5

# Reiniciar
./stop.sh
./start.sh
```

#### Ollama responde lentamente
**Síntoma:** Respuestas tardan mucho

**Solución:**
```bash
# Modelo demasiado grande para hardware
# Usar modelo más pequeño:
docker exec ollama ollama pull mistral  # Más rápido que llama3.2

# Cambiar en workflow n8n
# "model": "mistral" en lugar de "llama3.2"

# O usar CPU en lugar de GPU
./start.sh --cpu
```

#### ComfyUI genera lentamente
**Síntoma:** Images tardan mucho

**Solución:**
```bash
# Ver GPU usage
nvidia-smi  # NVIDIA
rocm-smi    # AMD

# Reducir resolucion en workflow
# Cambiar 512x512 a 256x256

# Usar modelo más pequeño
# En ComfyUI, seleccionar modelo comprimido

# O cambiar a CPU (más lento pero usa menos RAM)
./stop.sh
./start.sh --cpu
```

### Debugging avanzado

#### Habilitar logs verbose
```bash
# n8n con logs detallados
docker compose logs -f --tail=100 n8n

# Todos los servicios
docker compose logs -f

# Seguir logs en tiempo real de stderr
docker compose logs -f 2>&1 | grep ERROR
```

#### Acceder a shell dentro de contenedor
```bash
# n8n
docker exec -it n8n bash

# Ollama
docker exec -it ollama bash

# Ejecutar comandos
docker exec n8n npm list n8n
```

#### Inspeccionar volúmenes
```bash
# Ver contenido de volumen
docker run -v n8n_storage:/data -it alpine ls -la /data

# Crear backup
docker run -v n8n_storage:/data -v $(pwd):/backup alpine \
  tar czf /backup/n8n_backup.tar.gz /data
```

#### Reset completo
```bash
# Parar todo
./stop.sh

# Eliminar volúmenes (⚠️ Perderás todos los datos)
docker volume rm n8n_storage postgres_storage qdrant_storage ollama_storage

# Reset configuración
./uninitialize_env.sh

# Empezar de cero
cp .env.example .env
# Editar .env con nuevas credenciales
./start.sh
```

---

## 🤝 Contribución

Nos encantaría recibir contribuciones. Por favor:

1. **Fork** el repositorio
2. **Crea una rama** para tu feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** tus cambios (`git commit -m 'Add AmazingFeature'`)
4. **Push** a la rama (`git push origin feature/AmazingFeature`)
5. **Abre un Pull Request**

### Estándares de código

- **Bash scripts:** Shellcheck compatible, comentarios explicativos
- **Docker:** Usar `.dockerignore`, multi-stage builds cuando sea posible
- **YAML:** Indentación de 2 espacios
- **Documentación:** Mantener README y instrucciones actualizadas

Para más detalles, ver [CONTRIBUTING.md](CONTRIBUTING.md)

### Reporte de bugs

Usa [GitHub Issues](https://github.com/Axlfc/connect-core/issues) con:
- Descripción clara del problema
- Pasos para reproducir
- Versión de Docker & OS
- Logs relevantes

---

## 📄 Licencia

Este proyecto está licenciado bajo la **GNU Affero General Public License v3 (AGPL-3.0)**

- ✅ Puedes usar, modificar y distribuir
- ✅ Debes incluir aviso de cambios
- ✅ Si lo usas en red, debes compartir el código fuente
- 📖 [Ver licencia completa](LICENSE.md)

---

## 📞 Contacto & Recursos

- **GitHub:** [Axlfc/connect-core](https://github.com/Axlfc/connect-core)
- **Issues:** [GitHub Issues](https://github.com/Axlfc/connect-core/issues)
- **Guía de contribución:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Documentación técnica:** [.github/copilot-instructions.md](.github/copilot-instructions.md)

### Recursos útiles

- [n8n Documentation](https://docs.n8n.io/)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [Matrix Synapse Docs](https://matrix-org.github.io/synapse/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)

---

## 🙏 Agradecimientos

- **n8n** por la plataforma de automatización
- **Ollama** por hacer LLMs accesibles localmente
- **ComfyUI** por la generación de imágenes modular
- **Matrix** por la infraestructura de chat federado

---

<div align="center">

**Made with ❤️ by the cognito-stack team**

⭐ Si te resulta útil, ¡da una estrella!

</div>
