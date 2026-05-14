# AUDIT 12: VOICE GATEWAY AND SPECIALIZED SERVICES
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Clean Architecture** | The Voice Gateway is a well-designed microservice following FastAPI best practices. It acts as a decoupled orchestrator for STT, LLM, and TTS services. |
| ✓ | **Secure Configuration** | All configuration, including service URLs and the Redis password, is correctly managed via environment variables, avoiding hardcoded credentials. |
| ✓ | **Error Handling** | The code adequately handles network and HTTP status errors from downstream services, returning appropriate HTTP status codes (503 Service Unavailable, etc.). |
| ✗ | **Lack of Input Validation** | **CRITICAL:** The transcription endpoint (`/v1/audio/transcriptions`) **does not validate the uploaded audio file size**. An attacker could upload a maliciously large audio file, exhausting memory and CPU resources of the gateway and the Whisper service, causing a denial of service. |
| ⚠️ | **No Aggressive Timeouts** | While the HTTP client has a general 120-second timeout, individual requests to AI services (which can take a long time) do not have shorter, specific timeouts, which could leave connections open for a long time. |
| ⚠️ | **Overly Permissive CORS** | The CORS policy is configured with `allow_origins=["*"]`, allowing any website on the internet to make requests to the gateway. Although the gateway is protected by Authelia, this is an overly permissive configuration for production. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Asynchronous and Efficient Code:**
    *   The use of `FastAPI` along with `httpx.AsyncClient` ensures that the gateway is non-blocking and can handle multiple concurrent requests efficiently.

2.  **Caching Layer:**
    *   Implementing a Redis cache for Text-to-Speech (TTS) requests is an excellent optimization. It reduces load on the Kokoro service (which is GPU-intensive) and drastically improves response times for common phrases.

3.  **OpenAI API Compatibility:**
    *   The endpoints (`/v1/audio/transcriptions`, `/v1/audio/speech`) mimic the OpenAI API structure, facilitating integration with existing clients and tools.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **VG-01** | **CRITICAL** | **File Upload Without Size Limit** | The `create_transcription` endpoint reads the audio file completely into memory (`await file.read()`) without checking its size first. An attacker can send a file of several gigabytes, which will cause a `MemoryError` and lock the server process, making it inaccessible to other users (Denial of Service). |
| **VG-02** | **MEDIUM** | **Open CORS (`*`)** | Allowing `*` origins is poor practice in production. Although Authelia blocks unauthenticated access, this could still allow certain types of attacks (like CSRF in old browsers) and does not follow the principle of least privilege. |

---

### ⚠️ Warnings/Recommendations

1.  **WebSocket Security:**
    *   The current service does not use WebSockets, but if they were added in the future for real-time streaming, it would be crucial to implement origin (`Origin`) validation and message rate limiting to prevent abuse.

2.  **Audio Data Handling:**
    *   Audio data is processed in memory and in temporary files. While functional, there is no explicit cleanup or retention policy. It must be ensured that temporary files are always deleted, even in case of error. The current code (`os.unlink(tmp_path)`) is good but could be more robust if it were in a `finally` block.

3.  **Information in Logs:**
    *   `config.py` prints internal service URLs in the logs on startup. While useful for debugging, in a production environment, this could be considered a minor information leak about the internal architecture.

---

### 🔧 Suggested Solutions

1.  **For VG-01 (Validate Upload Size - CRITICAL):**
    *   **Solution:** Modify the `create_transcription` endpoint to validate the file size before reading it into memory.
        ```python
        # In main.py, inside create_transcription
        import config

        # ...

        # Read file content in chunks to check size
        # without loading it all into memory at once.
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

        # Now 'content' is safe to use
        files = {"audio_file": (file.filename, content, file.content_type)}
        response = await client.post(
            f"{config.WHISPER_URL}/asr",
            files=files,
            params={"output": "json"}
        )
        # ... rest of function
        ```
    *   `MAX_FILE_SIZE` should be configurable via `config.py`.

2.  **For VG-02 (Restrict CORS):**
    *   **Solution:** Modify the CORS configuration in `main.py` to only allow domains of the frontend applications that need to access the gateway.
        ```python
        # In main.py

        # Read allowed origins from an environment variable
        ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["https://n8n.localhost", "https://app.localhost"],
            allow_credentials=True,
            allow_methods=["GET", "POST"], # Be explicit
            allow_headers=["Authorization", "Content-Type"], # Be explicit
        )
        ```
