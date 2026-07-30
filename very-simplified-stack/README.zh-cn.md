# 🧠 极简 AI 堆栈 — 轻量级认知智能平台
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)

这是 AI 堆栈的精简和“极其简化”的版本。它专为希望获得核心 AI 编排能力和本地认知智能工具，但更喜欢在外部或另一台专用宿主机上运行 LLM（如 Ollama）的用户而设计。

这个简化堆栈的核心围绕 **Cognito Agent（Cognito 智能代理）** 构建，它原生集成了 **NOOA（NVIDIA-labs Object Oriented Agents）** 面向对象代理范式和 AGI 智能代理路线图的 5 个阶段。

---

## 🚀 包含哪些服务？

- **PostgreSQL**: 关系型数据库，集成向量检索扩展（`pgvector`）。
- **Qdrant**: 高性能向量数据库，用于语义搜索和 RAG 管道。
- **Redis**: 超高速内存缓存，用于会话和代理状态管理。
- **Forgejo**: 自托管 Git 服务，用于管理您的代码、仓库和 Webhook。
- **ComfyUI**: 具有原生 Stable Diffusion 支持的高级 AI 图像生成服务。
- **Voice Services**: 高性能语音服务，集成 Whisper (STT)、Kokoro (TTS) 和 Demucs (音频分离)。
- **Voice Gateway**: 统一的 API 网关，用于所有语音相关的处理任务。
- **Nginx Proxy & zrok**: 灵活的反向代理和安全隧道，用于公共 Webhook 的远程安全公开。
- **Cognito Backend (`cognito-backend`)**: 智能控制平面、多模型 AI 路由分发器和代理循环编排器。
- **Cognito Worker (`cognito-worker`)**: 宿主机端（host-side）安全执行组件，负责管理 Git 工作树、编译代码和验证代理生成的修复补丁。

---

## ❌ 移除了哪些服务？

为了保持此堆栈尽可能轻量、敏捷，我们移除了以下非核心服务：
- **Obsidian**: 本地知识库管理。
- **Drupal**: 门户 CMS / Web UI 实验层。
- **Monitoring**: Prometheus、Grafana、Alertmanager 监控面板。
- **其他支持工具**: LibreTranslate、LanguageTool、Duplicati 备份、Uptime Kuma。

---

## 🤖 Cognito Agent 架构深度剖析

该堆栈的认知智能分布在两个极为稳健的原生组件中：

### 1. 控制平面：`cognito-backend`
后端基于 FastAPI 框架构建，作为整个架构的大脑：
- **代理执行循环 (SSE)**: 提供 `/api/agent/loop` 端点，执行交互式思考推理和异步系统工具调用。
- **NOOAMeta 元类**: 自动将仅用省略号（`...`）声明的抽象生成方法包装为结构化的 LLM 推理调用，并严格强制执行 Pydantic 实体类型约定。
- **选择性可见性**: 使用 `@hidden` 修饰符或下划线前缀，将特定的敏感方法/属性从 LLM 提示词上下文里过滤隐藏。
- **自动上下文压缩**: 当会话 Token 数量超过最大限制（默认 8000）时，系统会自动在运行时生成上下文摘要并整理历史记录。
- **基于不确定性的自适应升级**: 如果当前模型在子任务中产生了过高的香农熵（不确定性），编排器会自动将其升级分发给更高参数的推理模型（如 GPT-4o、Claude），以确保最终修复质量。

### 2. 执行平面：`cognito-worker`
安全运行在宿主机端，以守护进程运行，处理繁重的文件系统和执行任务：
- **Git Worktree 安全隔离**: 在独立的临时 Git 工作树中签出和克隆目标仓库，以便在其中安全编译和运行测试套件，绝不污染或干扰用户当前处于活跃状态的分支。
- **HMAC 密码学安全校验**: 采用共享密钥机制对所有请求数据执行 HMAC 签名与时间戳校验，彻底杜绝请求伪造和重放攻击。
- **沙箱运行 SandboxExecutor**: 监控 Python 子进程执行，限制 CPU 核心、最大内存配额并应用严格的运行超时。

---

## 🛠️ 开始使用（安装与启动）

> **注意**: 此堆栈假定您在外部运行 [Ollama](https://ollama.com/)（例如，在宿主机或另一台专用服务器上）。默认情况下，它已预配置为连接到 `http://host.docker.internal:11434`。

### 步骤 1：配置环境变量
复制模板并在 `.env` 文件中设置您的密码、密钥和专属配置：
```bash
cp .env.example .env
nano .env
```
确保将 `OLLAMA_API_URL` 和 `OLLAMA_URL` 变量指向您真实的 Ollama 访问地址。

### 步骤 2：启动容器堆栈
选择与您的系统硬件配置相匹配的启动命令：

- **CPU 运行模式（无可用 GPU）**:
  ```bash
  docker compose --profile cpu --profile voice-cpu up -d
  ```

- **NVIDIA GPU 运行模式**:
  ```bash
  docker compose --profile gpu-nvidia --profile voice up -d
  ```

- **启用公网 zrok 隧道**:
  在上述命令的基础上添加 `--profile zrok` 参数。

### 步骤 3：在宿主机上启动 Cognito Worker（可选项，供 Agent 执行使用）
激活宿主机端工作空间执行守护进程：
```bash
cd cognito-worker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

---

## 💡 我们能用这个堆栈做什么？

极简 AI 堆栈运行起来后，您将拥有一个极其强大的认知 AI 环境，能够：

1. **部署自主编写代码的 AI 智能代理**:
   通过调用 `cognito-backend` 的 API 或运行轻量级 Python 客户端（`python -m cli.cognito_cli`）与您本地的项目代码对话。代理可以安全读取、编辑、编写文件或执行终端命令，同时严格遵守文件保护和项目受信任声明。
2. **执行 5 阶段完整 AGI 流程**:
   利用 `agents/` 模块分解复杂工作（阶段 1：思维链）、验证输出结果并自动迭代反馈（阶段 2）、从过去的执行中学习（阶段 3）、协调多智能体分发路由（阶段 4）以及优化计算资源配置（阶段 5）。
3. **安全知识 RAG 与语义搜索**:
   将您本地的威胁模型、架构设计或 markdown 规范文档导入 Qdrant 中，允许您的代理在实时交互中检索这些上下文，答复复杂的专业问题。
4. **本地音频和语音处理**:
   使用 Kokoro 文本转语音、使用 Whisper 语音转文本、或使用 Demucs 进行伴奏人声分离，一切只需通过统一的 Voice Gateway 门禁。
