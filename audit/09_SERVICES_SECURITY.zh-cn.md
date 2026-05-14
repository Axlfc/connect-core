# AUDIT 09：核心服务 - 深度审查
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✗ | **n8n (自动化)** | **关键：** `task-runners` 配置完全禁用了沙箱，允许任何可以创建工作流的用户在运行器容器中**执行任意代码**。 |
| ✗ | **Ollama (LLMs)** | `ollama-proxy` 是一个简单的直通代理，**没有任何安全层**。它没有实现频率限制 (rate limiting)、API 密钥访问控制或请求日志，完全依赖 Authelia 进行保护。 |
| ⚠️ | **ComfyUI (图像)** | 禁用了原生身份验证 (`WEB_ENABLE_AUTH=false`)，导致**完全依赖 Authelia**。如果绕过了 Authelia，图像生成服务将完全暴露，容易受到资源滥用。 |
| ✗ | **Matrix (消息传递)** | **关键：** Matrix 容器的入口点脚本在首次运行时**在日志中暴露了关键机密**。此外，用户注册在 `.env.staging` 中默认启用，这可能允许不必要的注册。 |
| ⚠️ | **Qdrant (向量数据库)** | 该服务未配置任何 API 密钥用于访问，这意味着同一 Docker 网络 (`ai`) 中的任何服务都可以在未经身份验证的情况下对向量数据库进行读写。 |

---

## 2. 详细发现

### a) n8n (工作流自动化)

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **S-n8n-01** | **关键** | **运行器沙箱已禁用** | `n8n-task-runners.json` 文件将 `NODE_FUNCTION_ALLOW_BUILTIN` 和 `N8N_RUNNERS_STDLIB_ALLOW` 配置为 `*`。这允许有权访问 n8n 的用户在“Code”节点中使用 `child_process` 或 `fs` 等模块，从而在运行器容器内获得完整的 Shell。攻击者可以窃取数据、攻击内部网络中的其他服务或安装恶意软件。 |

#### 🔧 建议的解决方案 (n8n)

*   **即刻方案：** 修改 `n8n-task-runners.json` 以实施严格的“黑名单”或“白名单”策略。显式拒绝访问危险的系统模块。
    ```json
    // 在 n8n-task-runners.json 中，针对 javascript 运行器
    "env-overrides": {
        "NODE_FUNCTION_DENY_BUILTIN": "fs,os,child_process,worker_threads,vm",
        "NODE_FUNCTION_ALLOW_EXTERNAL": "axios,moment" // 仅允许特定模块
    }
    ```

### b) Ollama (本地 LLM)

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **S-ollama-01** | **高** | **代理缺乏额外安全性** | `ollama-proxy` 只是一个简单的转发代理，不提供任何安全价值。如果 Authelia 失效或配置错误，就没有第二道防线。攻击者可以滥用 LLM 模型，大规模且无控制地消耗 GPU/CPU 资源。 |

#### 🔧 建议的解决方案 (Ollama)

*   **解决方案：** 改进 `ollama-proxy` 以使其充当真正的“API 网关”。
    1.  **添加频率限制：** 在 `server.js` 中实现中间件（例如 `express-rate-limit`）以限制每个 IP 的请求数。
    2.  **添加日志：** 记录每个请求（IP, 端点, 时间戳）以便能够检测滥用行为。
    3.  **(可选) API 密钥身份验证：** 实现 API 密钥系统，内部服务（如 n8n）必须使用该密钥才能访问 Ollama，从而提供额外的身份验证层。

### c) ComfyUI (图像生成)

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **S-comfy-01** | **中** | **唯一依赖 Authelia** | 通过禁用 ComfyUI 的原生身份验证，所有安全性都落在了边界层。这违反了“深度防御”原则。Nginx 或 Authelia 的配置错误将导致服务完全失去保护。 |

#### 🔧 建议的解决方案 (ComfyUI)

*   **解决方案：** 启用 ComfyUI 原生身份验证作为第二道防线。
    1.  **修改 `docker-compose.yml`：**
        ```diff
        -      - WEB_ENABLE_AUTH=false
        +      - WEB_ENABLE_AUTH=true
        ```
    2.  **管理凭据：** ComfyUI 的凭据（用户名/密码）应通过 Docker Secrets 进行管理，方式与其他服务的建议相同。

### d) Matrix (消息传递)

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **S-matrix-01** | **关键** | **日志中暴露机密** | 如 **审计 04 (DS-02)** 中所述，Matrix 容器的入口点在首次启动时将服务器机密打印在 Docker 日志中。 |
| **S-matrix-02** | **高** | **默认开启用户注册** | 在 `.env.staging` 文件中，变量 `MATRIX_ENABLE_REGISTRATION` 配置为 `true`。如果此配置进入生产环境，它将允许任何人注册到消息服务器，从而引发垃圾信息、滥用和资源消耗。 |

#### 🔧 建议的解决方案 (Matrix)

*   **针对 S-matrix-01：** 请参阅 `04_DOCKER_SECURITY.md` 中的详细解决方案。
*   **针对 S-matrix-02：**
    *   **解决方案：** 将 `.env.example` 和 `.env.staging` 中的默认值更改为 `false`。用户注册应该是管理员控制下的显式操作。
        ```diff
        # 在 .env.example 和 .env.staging 中
        - MATRIX_ENABLE_REGISTRATION=true
        + MATRIX_ENABLE_REGISTRATION=false
        ```

### e) Qdrant (向量数据库)

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **S-qdrant-01** | **中** | **内部网络未经身份验证的访问** | Qdrant 支持 API 密钥身份验证，但目前尚未配置。`ai` 网络中的任何容器（无论是受攻破的还是合法的）都可以访问、修改和删除向量数据库中的数据。 |

#### 🔧 建议的解决方案 (Qdrant)

*   **解决方案：** 启用 API 密钥身份验证。
    1.  **生成 API 密钥：** 使用 `openssl rand -hex 32` 并将其保存为 Docker Secret。
    2.  **修改 Qdrant 的 `docker-compose.yml`：**
        ```yaml
        # 在 qdrant 服务中
        secrets:
          - qdrant_api_key
        command: ["./qdrant", "--api-key-file", "/run/secrets/qdrant_api_key"]
        ```
    3.  **更新客户端：** 配置使用 Qdrant 的服务（如 n8n），使其在请求中发送 API 密钥。
