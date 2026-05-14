# 审计 12：语音网关与专用服务
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/12_VOICE_GATEWAY.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/12_VOICE_GATEWAY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/12_VOICE_GATEWAY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/12_VOICE_GATEWAY.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **架构整洁** | 语音网关是一个设计良好的微服务，遵循了 FastAPI 的最佳实践。它充当 STT、LLM 和 TTS 服务之间的解耦编排器。 |
| ✓ | **配置安全** | 所有配置（包括服务 URL 和 Redis 密码）均通过环境变量正确管理，避免了硬编码凭据。 |
| ✓ | **错误处理** | 代码能够妥善处理来自下游服务的网络错误和 HTTP 状态错误，并返回合适的 HTTP 状态码（503 Service Unavailable 等）。 |
| ✗ | **缺少输入验证** | **关键：** 转录端点 (`/v1/audio/transcriptions`) **未对上传的音频文件大小进行验证**。攻击者可能上传恶意的大体积音频文件，耗尽网关和 Whisper 服务的内存及 CPU 资源，从而导致拒绝服务攻击。 |
| ⚠️ | **未设置严格超时** | 虽然 HTTP 客户端有 120 秒的总超时限制，但对 AI 服务（可能耗时较长）的单个请求没有更短、更具体的超时设置，这可能导致连接长时间被占用。 |
| ⚠️ | **CORS 过于宽松** | CORS 策略配置为 `allow_origins=["*"]`，允许互联网上的任何网站向网关发起请求。虽然网关受 Authelia 保护，但这对于生产环境来说仍是过于宽松的配置。 |

---

## 2. 详细发现

### ✓ 优点

1.  **异步且高效的代码：**
    *   使用 `FastAPI` 配合 `httpx.AsyncClient` 确保了网关是非阻塞的，能够高效处理多个并发请求。

2.  **缓存层：**
    *   在 Redis 中为文本转语音 (TTS) 请求实现缓存是一项极佳的优化。它减轻了 Kokoro 服务（高 GPU 消耗）的负担，并显著缩短了常用短语的响应时间。

3.  **兼容 OpenAI API：**
    *   端点（`/v1/audio/transcriptions`, `/v1/audio/speech`）模仿了 OpenAI API 的结构，便于与现有客户端和工具集成。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **VG-01** | **关键** | **文件上传无大小限制** | `create_transcription` 端点将音频文件完整读取到内存中 (`await file.read()`)，而没有预先检查大小。攻击者可以发送数 GB 的文件，这将导致 `MemoryError` 并阻塞服务器进程，使其对其他用户不可用（拒绝服务）。 |
| **VG-02** | **中** | **CORS 全开放 (`*`)** | 允许 `*` 来源是生产环境中的不良实践。虽然 Authelia 阻止了未经身份验证的访问，但这仍可能允许某些类型的攻击（如旧版浏览器中的 CSRF），且不符合最小权限原则。 |

---

### ⚠️ 警告/建议

1.  **WebSocket 安全性：**
    *   目前的服务不使用 WebSocket，但如果将来添加实时流功能，实施来源 (`Origin`) 验证和消息频率限制以防止滥用将至关重要。

2.  **音频数据处理：**
    *   音频数据在内存和临时文件中处理。虽然功能正常，但没有明确的清理或保留策略。应确保临时文件始终被删除，即使发生错误也不例外。目前的代码 (`os.unlink(tmp_path)`) 很好，但如果放在 `finally` 块中会更稳健。

3.  **日志信息：**
    *   `config.py` 在启动时将内部服务的 URL 打印在日志中。虽然有助于调试，但在生产环境中，这可能被视为有关内部架构的小规模信息泄露。

---

### 🔧 建议的解决方案

1.  **针对 VG-01（验证上传大小 - 关键）：**
    *   **解决方案：** 修改 `create_transcription` 端点，在将文件读取到内存之前验证其大小。
        ```python
        # 在 main.py 的 create_transcription 函数中
        import config

        # ...

        # 分块读取文件内容以检查大小，
        # 而不是一次性全部加载到内存中。
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

        size = 0
        chunks = []
        async for chunk in file.file:
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, detail=f"文件大小超过限制：{MAX_FILE_SIZE / 1024 / 1024} MB"
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        # 现在使用 'content' 是安全的
        files = {"audio_file": (file.filename, content, file.content_type)}
        response = await client.post(
            f"{config.WHISPER_URL}/asr",
            files=files,
            params={"output": "json"}
        )
        # ... 函数的其余部分
        ```
    *   `MAX_FILE_SIZE` 应该可以通过 `config.py` 进行配置。

2.  **针对 VG-02（限制 CORS）：**
    *   **解决方案：** 修改 `main.py` 中的 CORS 配置，仅允许需要访问网关的前端应用域名。
        ```python
        # 在 main.py 中

        # 从环境变量读取允许的来源
        ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["https://n8n.localhost", "https://app.localhost"],
            allow_credentials=True,
            allow_methods=["GET", "POST"], # 明确指定
            allow_headers=["Authorization", "Content-Type"], # 明确指定
        )
        ```
