# AUDIT 09: CORE SERVICES - DEEP REVIEW
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✗ | **n8n (Automation)** | **CRITICAL:** The `task-runners` configuration completely disables sandboxing, allowing **arbitrary code execution** in the runner container by any user who can create a workflow. |
| ✗ | **Ollama (LLMs)** | The `ollama-proxy` is a simple pass-through proxy **without any security layer**. It does not implement rate limiting, API key access control, or request logging, relying exclusively on Authelia for protection. |
| ⚠️ | **ComfyUI (Images)** | Native authentication is disabled (`WEB_ENABLE_AUTH=false`), creating a **total dependency on Authelia**. If Authelia were bypassed, the image generation service would be completely exposed and vulnerable to resource abuse. |
| ✗ | **Matrix (Messaging)** | **CRITICAL:** The Matrix container entrypoint script **exposes critical secrets in the logs** during the first execution. Additionally, user registration is enabled by default in `.env.staging`, which could allow unwanted signups. |
| ⚠️ | **Qdrant (Vector DB)** | The service has no API key configured for access, meaning any service within the same Docker network (`ai`) can read and write to the vector database without authentication. |

---

## 2. Detailed Findings

### a) n8n (Workflow Automation)

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **S-n8n-01** | **CRITICAL** | **Sandboxing Disabled in Runners** | The `n8n-task-runners.json` file configures `NODE_FUNCTION_ALLOW_BUILTIN` and `N8N_RUNNERS_STDLIB_ALLOW` with `*`. This allows a user with n8n access to use modules like `child_process` or `fs` in a "Code" node, giving them a full shell inside the runner container. They could exfiltrate data, attack other services in the internal network, or install malware. |

#### 🔧 Suggested Solution (n8n)

*   **Immediate Solution:** Modify `n8n-task-runners.json` to implement a strict "deny-list" or "allow-list" policy. Explicitly deny access to dangerous system modules.
    ```json
    // In n8n-task-runners.json, for the javascript runner
    "env-overrides": {
        "NODE_FUNCTION_DENY_BUILTIN": "fs,os,child_process,worker_threads,vm",
        "NODE_FUNCTION_ALLOW_EXTERNAL": "axios,moment" // Allow only specific modules
    }
    ```

### b) Ollama (Local LLMs)

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **S-ollama-01** | **HIGH** | **Proxy without Additional Security** | The `ollama-proxy` is a simple forwarding proxy. It adds no security value. If Authelia fails or is misconfigured, there is no second layer of defense. An attacker could abuse LLM models, consuming GPU/CPU resources massively and without control. |

#### 🔧 Suggested Solution (Ollama)

*   **Solution:** Improve `ollama-proxy` to act as a true "API Gateway".
    1.  **Add Rate Limiting:** Implement middleware in `server.js` (e.g., `express-rate-limit`) to limit the number of requests per IP.
    2.  **Add Logging:** Record each request (IP, endpoint, timestamp) to detect abuse.
    3.  **(Optional) API Key Authentication:** Implement an API key system that internal services (like n8n) must use to access Ollama, providing an additional layer of authentication.

### c) ComfyUI (Image Generation)

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **S-comfy-01** | **MEDIUM** | **Single Dependency on Authelia** | By disabling ComfyUI's native authentication, all security falls on the perimeter layer. This violates the "defense in depth" principle. A configuration error in Nginx or Authelia would leave the service totally unprotected. |

#### 🔧 Suggested Solution (ComfyUI)

*   **Solution:** Enable ComfyUI native authentication as a second layer of defense.
    1.  **Modify `docker-compose.yml`:**
        ```diff
        -      - WEB_ENABLE_AUTH=false
        +      - WEB_ENABLE_AUTH=true
        ```
    2.  **Manage Credentials:** ComfyUI credentials (user/password) should be managed via Docker Secrets, in the same way suggested for other services.

### d) Matrix (Messaging)

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **S-matrix-01** | **CRITICAL** | **Secrets Exposed in Logs** | As detailed in **AUDIT 04 (DS-02)**, the Matrix container entrypoint prints server secrets in Docker logs on the first boot. |
| **S-matrix-02** | **HIGH** | **User Registration Open by Default** | The `MATRIX_ENABLE_REGISTRATION` variable is set to `true` in the `.env.staging` file. If this configuration reaches production, it would allow anyone to register on the messaging server, opening the door to spam, abuse, and resource consumption. |

#### 🔧 Suggested Solution (Matrix)

*   **For S-matrix-01:** See the detailed solution in `04_DOCKER_SECURITY.md`.
*   **For S-matrix-02:**
    *   **Solution:** Change the default value in `.env.example` and `.env.staging` to `false`. User registration should be an explicit and administrator-controlled action.
        ```diff
        # In .env.example and .env.staging
        - MATRIX_ENABLE_REGISTRATION=true
        + MATRIX_ENABLE_REGISTRATION=false
        ```

### e) Qdrant (Vector Database)

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **S-qdrant-01** | **MEDIUM** | **Unauthenticated Access on Internal Network** | Qdrant supports API key authentication, but it is not configured. Any container on the `ai` network (compromised or legitimate) can access, modify, and delete data from the vector database. |

#### 🔧 Suggested Solution (Qdrant)

*   **Solution:** Enable API key authentication.
    1.  **Generate an API Key:** Use `openssl rand -hex 32` and save it as a Docker Secret.
    2.  **Modify `docker-compose.yml` for Qdrant:**
        ```yaml
        # In the qdrant service
        secrets:
          - qdrant_api_key
        command: ["./qdrant", "--api-key-file", "/run/secrets/qdrant_api_key"]
        ```
    3.  **Update Clients:** Configure services using Qdrant (like n8n) to send the API key in their requests.
