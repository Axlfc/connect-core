# 🧠 Very Simplified AI Stack — Stack de Inteligencia Artificial Simplificado
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)

Esta es una versión refinada y "extremadamente simplificada" del AI Stack. Está diseñada para usuarios que desean capacidades centrales de orquestación de IA y herramientas cognitivas locales, pero prefieren ejecutar sus LLMs (como Ollama) de forma externa o en otra máquina dedicada del host.

El núcleo de este stack simplificado se centra en el **Agente Cognito (Cognito Agent)**, el cual integra de forma nativa el paradigma **NOOA (NVIDIA-labs Object Oriented Agents)** y las 5 fases del Roadmap de AGI.

---

## 🚀 ¿Qué Incluye?

- **PostgreSQL**: Base de datos relacional con extensión vectorial integrada (`pgvector`).
- **Qdrant**: Base de datos vectorial de alto rendimiento para búsqueda semántica y RAG.
- **Redis**: Servidor de caché en memoria ultra-rápido para gestión de sesiones de IA.
- **Forgejo**: Servidor Git self-hosted para gestionar tu código, repositorios y webhooks.
- **ComfyUI**: Generación de imágenes avanzada con soporte nativo de Stable Diffusion.
- **Voice Services**: Integración de Whisper (STT), Kokoro (TTS) y Demucs (separación de audio).
- **Voice Gateway**: API unificada y pasarela para simplificar tareas de procesamiento de voz.
- **Nginx Proxy & zrok**: Servidor proxy y tunelización segura para webhooks públicos.
- **Cognito Backend (`cognito-backend`)**: Plano de control inteligente, enrutador multi-modelo de IA (Ollama, Codex) y orquestador del bucle del agente.
- **Cognito Worker (`cognito-worker`)**: Componente de ejecución segura del lado del host que realiza aislamiento de repositorios (`git worktree`), compilación y verificación de cambios.

---

## ❌ ¿Qué se ha eliminado?

Para mantener el stack lo más ligero y ágil posible, se han descartado:
- **Obsidian**: Gestor de base de conocimientos local.
- **Drupal**: Capa CMS / experimentación web de UI.
- **Monitoreo**: Servidores Prometheus, Grafana, Alertmanager, etc.
- **Herramientas de soporte**: LibreTranslate, LanguageTool, Duplicati, Uptime Kuma.

---

## 🤖 El Agente Cognito y su Arquitectura

La inteligencia del stack está distribuida en dos componentes nativos sumamente robustos:

### 1. Plano de Control: `cognito-backend`
El backend (desarrollado en FastAPI) actúa como el cerebro de la arquitectura:
- **Bucle de Agente (SSE)**: Expone el endpoint `/api/agent/loop` que ejecuta razonamiento interactivo y llamadas asíncronas a herramientas de sistema.
- **Metaclase NOOAMeta**: Permite definir clases de agente donde los métodos vacíos especificados únicamente con el elipsis (`...`) son envueltos automáticamente en llamadas estructuradas de LLM, respetando contratos de tipo Pydantic de forma estricta.
- **Visibilidad Selectiva**: Oculta métodos y atributos marcados con `@hidden` o guión bajo del contexto del LLM.
- **Compactado Automático**: Reduce el historial de la conversación mediante resúmenes de contexto en caliente para no saturar la ventana de tokens.
- **Escalado Adaptativo por Incertidumbre**: Si el modelo actual genera una subtarea con alta entropía de Shannon (incertidumbre), el orquestador la escala automáticamente a un modelo de mayor rango (como GPT-4o o Claude) para garantizar la calidad.

### 2. Capa de Ejecución Segura: `cognito-worker`
El worker (desarrollado en Python con uvicorn) corre del lado del host de forma segura:
- **Aislamiento con Git Worktree**: Clonado seguro de repositorios en directorios temporales para validar parches y pruebas sin colisionar con la rama de desarrollo activa del usuario.
- **Firma Criptográfica HMAC**: Todas las comunicaciones entre el backend y el worker se firman y validan mediante un secreto HMAC compartido para evitar ataques de manipulación o replay.
- **Sandboxing SandboxExecutor**: Ejecuta código generado por el LLM en un entorno aislado aplicando límites estrictos de recursos de hardware y tiempos de espera (timeouts).

---

## 🛠️ Puesta en Marcha (Instalación y Arranque)

> **Nota**: Este stack asume que tienes [Ollama](https://ollama.com/) ejecutándose de forma externa (por ejemplo, en el host o en otro servidor). Por defecto, está preconfigurado para conectarse a `http://host.docker.internal:11434`.

### Paso 1: Configurar Variables de Entorno
Copia la plantilla y configura tus claves y contraseñas secretas en el archivo `.env`:
```bash
cp .env.example .env
nano .env
```
Asegúrate de apuntar las variables `OLLAMA_API_URL` y `OLLAMA_URL` hacia tu endpoint de Ollama correspondiente.

### Paso 2: Arrancar los Contenedores
Selecciona el comando adecuado según el hardware de tu servidor o máquina:

- **Modo CPU (Sin GPU)**:
  ```bash
  docker compose --profile cpu --profile voice-cpu up -d
  ```

- **Modo GPU NVIDIA**:
  ```bash
  docker compose --profile gpu-nvidia --profile voice up -d
  ```

- **Con Tunelización Pública (zrok)**:
  Añade `--profile zrok` a cualquiera de las instrucciones anteriores.

### Paso 3: Arrancar el Cognito Worker en el Host (Opcional para automatizaciones)
Para configurar el componente de ejecución segura en segundo plano del lado del host:
```bash
cd cognito-worker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

---

## 💡 ¿Qué Podemos Hacer con Esto?

Una vez levantado el stack, tienes un entorno cognitivo de desarrollo extremadamente potente para:

1. **Crear e Instanciar Agentes Autónomos**:
   Usa el API de `cognito-backend` o la CLI interactiva en Python (`python -m cli.cognito_cli`) para dialogar con tu repositorio, permitiendo al agente leer, editar, escribir archivos o ejecutar comandos bash de forma autónoma con total seguridad y control de trust.
2. **Ejecutar pipelines de AGI de 5 fases**:
   Usa el módulo `agents/` para descomponer tareas complejas (fase 1: Chain-of-Thought), validar salidas con auto-iteración y feedback en caliente (fase 2: Self-Evaluation), aprender de ejecuciones pasadas (fase 3: Memory & Learning), coordinar equipos con el enrutador inteligente de agentes (fase 4) y optimizar recursos (fase 5).
3. **Flujos RAG y Búsqueda Semántica**:
   Ingesta documentos, modelos de amenaza o guías de arquitectura locales en Qdrant, permitiendo a tus agentes consultar y responder preguntas complejas con contexto enriquecido en tiempo real.
4. **Separación y Procesamiento de Voz Local**:
   Convierte texto a voz de alta calidad con Kokoro, transcribe audios con Whisper o separa pistas musicales con Demucs mediante el Voice Gateway unificado.
