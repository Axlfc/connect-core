# AUDIT 09: SERVICIOS PRINCIPALES - REVISIÓN PROFUNDA
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/09_SERVICES_SECURITY.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/09_SERVICES_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/09_SERVICES_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/09_SERVICES_SECURITY.ca.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✗ | **n8n (Automatización)** | **CRÍTICO:** La configuración de los `task-runners` deshabilita completamente el sandboxing, permitiendo la **ejecución de código arbitrario** en el contenedor del runner por cualquier usuario que pueda crear un workflow. |
| ✗ | **Ollama (LLMs)** | El `ollama-proxy` es un simple proxy de paso **sin ninguna capa de seguridad**. No implementa rate limiting, control de acceso por API key, ni logging de peticiones, dependiendo exclusivamente de Authelia para su protección. |
| ⚠️ | **ComfyUI (Imágenes)** | La autenticación nativa está deshabilitada (`WEB_ENABLE_AUTH=false`), creando una **dependencia total en Authelia**. Si Authelia fuera bypassado, el servicio de generación de imágenes quedaría completamente expuesto y vulnerable a abuso de recursos. |
| ✗ | **Matrix (Mensajería)** | **CRÍTICO:** El script de entrypoint del contenedor de Matrix **expone secretos críticos en los logs** durante la primera ejecución. Además, la configuración de registro de usuarios está habilitada por defecto en el `.env.staging`, lo que podría permitir registros no deseados. |
| ⚠️ | **Qdrant (Vector DB)** | El servicio no tiene configurada ninguna clave de API para el acceso, lo que significa que cualquier servicio dentro de la misma red de Docker (`ai`) puede leer y escribir en la base de datos vectorial sin autenticación. |

---

## 2. Hallazgos Detallados

### a) N8N (Workflow Automation)

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **S-n8n-01** | **CRÍTICO** | **Sandboxing Deshabilitado en Runners** | El archivo `n8n-task-runners.json` configura `NODE_FUNCTION_ALLOW_BUILTIN` y `N8N_RUNNERS_STDLIB_ALLOW` con `*`. Esto permite a un usuario con acceso a n8n usar módulos como `child_process` o `fs` en un nodo de "Code", dándole un shell completo dentro del contenedor del runner. Podría exfiltrar datos, atacar otros servicios en la red interna o instalar malware. |

#### 🔧 解决方案 Sugerida (n8n)

*   **解决方案 Inmediata:** Modificar `n8n-task-runners.json` para implementar una política de "deny-list" o "allow-list" estricta. Denegar explícitamente el acceso a módulos peligrosos del sistema.
    ```json
    // En n8n-task-runners.json, para el runner de javascript
    "env-overrides": {
        "NODE_FUNCTION_DENY_BUILTIN": "fs,os,child_process,worker_threads,vm",
        "NODE_FUNCTION_ALLOW_EXTERNAL": "axios,moment" // Permitir solo módulos específicos
    }
    ```

### b) OLLAMA (LLMs Locales)

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **S-ollama-01** | **ALTO** | **Proxy sin Seguridad Adicional** | El `ollama-proxy` es un proxy de reenvío simple. No añade valor de seguridad. Si Authelia falla o es mal configurado, no hay una segunda capa de defensa. Un atacante podría abusar de los modelos de LLM, consumiendo recursos de GPU/CPU de forma masiva y sin control. |

#### 🔧 解决方案 Sugerida (Ollama)

*   **解决方案:** Mejorar el `ollama-proxy` para que actúe como un verdadero "API Gateway".
    1.  **Añadir Rate Limiting:** Implementar un middleware en `server.js` (ej. `express-rate-limit`) para limitar el número de peticiones por IP.
    2.  **Añadir Logging:** Registrar cada petición (IP, endpoint, timestamp) para poder detectar abusos.
    3.  **(Opcional) Autenticación por API Key:** Implementar un sistema de API keys que los servicios internos (como n8n) deban usar para acceder a Ollama, proporcionando una capa de autenticación adicional.

### c) COMFYUI (Generación de Imágenes)

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **S-comfy-01** | **MEDIO** | **Dependencia Única de Authelia** | Al deshabilitar la autenticación nativa de ComfyUI, toda la seguridad recae en la capa perimetral. Esto viola el principio de "defensa en profundidad". Un error de configuración en Nginx o Authelia dejaría el servicio totalmente desprotegido. |

#### 🔧 解决方案 Sugerida (ComfyUI)

*   **解决方案:** Habilitar la autenticación nativa de ComfyUI como segunda capa de defensa.
    1.  **Modificar `docker-compose.yml`:**
        ```diff
        -      - WEB_ENABLE_AUTH=false
        +      - WEB_ENABLE_AUTH=true
        ```
    2.  **Gestionar Credenciales:** Las credenciales de ComfyUI (usuario/contraseña) deberían ser gestionadas a través de Docker Secrets, de la misma manera que se sugiere para otros servicios.

### d) MATRIX (Mensajería)

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **S-matrix-01** | **CRÍTICO** | **Exposición de Secretos en Logs** | Como se detalla en el **AUDIT 04 (DS-02)**, el entrypoint del contenedor de Matrix imprime secretos de servidor en los logs de Docker en el primer arranque. |
| **S-matrix-02** | **ALTO** | **Registro de Usuarios Abierto por Defecto** | La variable `MATRIX_ENABLE_REGISTRATION` está configurada como `true` en el archivo `.env.staging`. Si esta configuración llega a producción, permitiría que cualquiera se registre en el servidor de mensajería, abriendo la puerta a spam, abuso y consumo de recursos. |

#### 🔧 解决方案 Sugerida (Matrix)

*   **Para S-matrix-01:** Ver la solución detallada en `04_DOCKER_SECURITY.md`.
*   **Para S-matrix-02:**
    *   **解决方案:** Cambiar el valor por defecto en `.env.example` y `.env.staging` a `false`. El registro de usuarios debe ser una acción explícita y controlada por el administrador.
        ```diff
        # En .env.example y .env.staging
        - MATRIX_ENABLE_REGISTRATION=true
        + MATRIX_ENABLE_REGISTRATION=false
        ```

### e) QDRANT (Vector Database)

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **S-qdrant-01** | **MEDIO** | **Acceso sin Autenticación en la Red Interna** | Qdrant soporta la autenticación mediante API key, pero esta no está configurada. Cualquier contenedor en la red `ai` (comprometido o legítimo) puede acceder, modificar y eliminar datos de la base de datos vectorial. |

#### 🔧 解决方案 Sugerida (Qdrant)

*   **解决方案:** Habilitar la autenticación por API key.
    1.  **Generar una API Key:** Usar `openssl rand -hex 32` y guardarla como un Docker Secret.
    2.  **Modificar `docker-compose.yml` para Qdrant:**
        ```yaml
        # En el servicio qdrant
        secrets:
          - qdrant_api_key
        command: ["./qdrant", "--api-key-file", "/run/secrets/qdrant_api_key"]
        ```
    3.  **Actualizar Clientes:** Configurar los servicios que usan Qdrant (como n8n) para que envíen la API key en sus peticiones.
