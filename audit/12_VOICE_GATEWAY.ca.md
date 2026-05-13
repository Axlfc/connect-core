# AUDIT 12: VOICE GATEWAY Y SERVICIOS ESPECIALIZADOS
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/12_VOICE_GATEWAY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/12_VOICE_GATEWAY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/12_VOICE_GATEWAY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/12_VOICE_GATEWAY.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Arquitectura Limpia** | El Voice Gateway es un microservicio bien diseñado que sigue las mejores prácticas de FastAPI. Actúa como un orquestador desacoplado para los servicios de STT, LLM y TTS. |
| ✓ | **Configuración Segura** | Toda la configuración, incluyendo URLs de servicios y la contraseña de Redis, se gestiona correctamente a través de variables de entorno, evitando credenciales hardcodeadas. |
| ✓ | **Manejo de Errores** | El código maneja adecuadamente los errores de red y de estado HTTP de los servicios downstream, devolviendo códigos de estado HTTP apropiados (503 Service Unavailable, etc.). |
| ✗ | **Falta de Validación de Entradas** | **CRÍTICO:** El endpoint de transcripción (`/v1/audio/transcriptions`) **no valida el tamaño del archivo de audio subido**. Un atacante podría subir un archivo de audio maliciosamente grande, agotando la memoria y los recursos de CPU del gateway y del servicio Whisper, provocando una denegación de servicio. |
| ⚠️ | **Sin Timeouts Agresivos** | Aunque el cliente HTTP tiene un timeout general de 120 segundos, las peticiones individuales a los servicios de IA (que pueden tardar mucho) no tienen timeouts más cortos y específicos, lo que podría dejar conexiones abiertas durante mucho tiempo. |
| ⚠️ | **CORS Demasiado Permisivo** | La política de CORS está configurada para `allow_origins=["*"]`, lo que permite que cualquier sitio web en internet realice peticiones al gateway. Aunque el gateway está protegido por Authelia, esta es una configuración demasiado permisiva para producción. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Código Asíncrono y Eficiente:**
    *   El uso de `FastAPI` junto con `httpx.AsyncClient` asegura que el gateway sea no bloqueante y pueda manejar múltiples peticiones concurrentes de manera eficiente.

2.  **Capa de Caching:**
    *   La implementación de un caché en Redis para las peticiones de Text-to-Speech (TTS) es una excelente optimización. Reduce la carga en el servicio Kokoro (que consume mucha GPU) y mejora drásticamente los tiempos de respuesta para frases comunes.

3.  **Compatibilidad con API de OpenAI:**
    *   Los endpoints (`/v1/audio/transcriptions`, `/v1/audio/speech`) imitan la estructura de la API de OpenAI, lo que facilita la integración con clientes y herramientas existentes.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **VG-01** | **CRÍTICO** | **Subida de Archivos Sin Límite de Tamaño** | El endpoint `create_transcription` lee el archivo de audio completamente en memoria (`await file.read()`) sin verificar su tamaño primero. Un atacante puede enviar un archivo de varios gigabytes, lo que causará un error de `MemoryError` y bloqueará el proceso del servidor, haciéndolo inaccesible para otros usuarios (Denegación de Servei). |
| **VG-02** | **MEDIO** | **CORS Abierto (`*`)** | Permitir orígenes `*` es una mala práctica en producción. Aunque Authelia bloquea el acceso no autenticado, esto aún podría permitir ciertos tipos de ataques (como CSRF en navegadores antiguos) y no sigue el principio de mínimo privilegio. |

### ⚠️ Warnings/Recomendaciones

1.  **Seguridad de WebSockets:**
    *   El servicio actual no utiliza WebSockets, pero si se añadieran en el futuro para streaming en tiempo real, sería crucial implementar una validación del origen (`Origin`) y rate limiting en los mensajes para prevenir abusos.

2.  **Manejo de Datos de Audio:**
    *   Los datos de audio se procesan en memoria y en archivos temporales. Aunque esto es funcional, no hay una política explícita de limpieza o retención. Se debe asegurar que los archivos temporales se eliminen siempre, incluso en caso de error. El código actual (`os.unlink(tmp_path)`) es bueno, pero podría ser más robusto si estuviera en un bloque `finally`.

3.  **Información en Logs:**
    *   El `config.py` imprime las URLs de los servicios internos en los logs al iniciar. Aunque útil para la depuración, en un entorno de producción, esto podría ser considerado una fuga de información menor sobre la arquitectura interna.

### 🔧 Soluciones Sugeridas

1.  **Para VG-01 (Validar Tamaño de Subida - CRÍTICO):**
    *   **Solució:** Modificar el endpoint `create_transcription` para validar el tamaño del archivo antes de leerlo en memoria.
        ```python
        # En main.py, dentro de create_transcription
        import config

        # ...

        # Leer el contenido del archivo en trozos para verificar el tamaño
        # sin cargarlo todo en memoria de una vez.
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

        size = 0
        chunks = []
        async for chunk in file.file:
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, detail=f"File size exceeds the limit of {MAX_FILE_SIZE / 1024 / 1024} MB"
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        # Ahora el 'content' es seguro de usar
        files = {"audio_file": (file.filename, content, file.content_type)}
        response = await client.post(
            f"{config.WHISPER_URL}/asr",
            files=files,
            params={"output": "json"}
        )
        # ... resto de la función
        ```
    *   El `MAX_FILE_SIZE` debería ser configurable a través de `config.py`.

2.  **Para VG-02 (Restringir CORS):**
    *   **Solució:** Modificar la configuración de CORS en `main.py` para que solo permita los dominios de las aplicaciones frontend que necesitan acceder al gateway.
        ```python
        # En main.py

        # Leer los orígenes permitidos desde una variable de entorno
        ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["https://n8n.localhost", "https://app.localhost"],
            allow_credentials=True,
            allow_methods=["GET", "POST"], # Ser explícito
            allow_headers=["Authorization", "Content-Type"], # Ser explícito
        )
        ```
