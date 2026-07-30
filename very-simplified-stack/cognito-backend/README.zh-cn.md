# 🧠 Cognito Backend AI — Uncertainty-Aware API
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.ca.md)

该后端为基于 Ollama 的模型提供具有额外**不确定性评分**的 OpenAI 兼容 API。它包括一个 PowerShell 配置文件，根据模型的置信度水平进行彩色编码标记渲染（蓝色 → 琥珀色 → 红色）。

## 🚀 主要特性

- **不确定性监控**: 实时计算每个Token的香农熵。
- **SSE流式丰富**: 向标准OpenAI兼容数据块中注入不确定性 (`uncertainty`) 评分。
- **PowerShell CLI**: 集成支持流式视觉反馈的 `cog` (文本) 和 `cogt` (语音) 命令。
- **多后端路由**: 具备级联故障转移逻辑 (GPU优先) 的优先级路由。

## 🛠️ 安装指南

### 1. 后端 (Python/FastAPI)
该后端作为 `very-simplified-stack` 的一部分通过 Docker Compose 运行。请确保您可以访问 Ollama 实例 (默认: `http://192.168.1.15:11434`)。

### 2. PowerShell 配置 (客户端)
安装 CLI 工具 (`cog`, `cogt`) 并启用不确定性可视化：

1. 打开 PowerShell。
2. 导航到此目录。
3. 运行安装程序：
   ```powershell
   .\Install-CognitoProfile.ps1
   ```
4. 重启 PowerShell。

## 🎨 不确定性可视化

CLI 使用以下颜色渐变来指示模型的置信度：
- 🔵 **蓝色** (低不确定性，高置信度)
- 🟡 **琥珀色** (中等不确定性，轻微犹豫)
- 🔴 **红色** (高不确定性，潜在的幻觉或复杂推理)

### 命令参数

- `-Threshold 0.6`: 覆盖默认的着色不确定性阈值。
- `-NoColor`: 禁用当前请求的所有着色（适用于管道输出）。
- `-NoTTS`: (对于 `cogt`) 禁用当前请求的文本转语音。

## ⚙️ 配置

配置加载的优先级顺序如下：
1. **命令行参数** (例如 `-Threshold`)
2. **环境变量**:
   - `COGNITO_UNCERTAINTY_THRESHOLD` (默认: `0.55`)
   - `COGNITO_ENABLE_UNCERTAINTY` (`true`/`false`)
   - `COGNITO_COLOR_MODE` (`full`, `threshold` 或 `none`)
3. **配置文件**: `~/.cognito/config.json`
4. **默认设置**

## 📂 项目结构

- `app/api/routes/openai_compat.py`: 核心流式处理和不确定性计算逻辑。
- `app/services/backend_client.py`: 统一的 Ollama 和 OpenAI 后端异步客户端。
- `test-voice-api.ps1`: 包含 `cog` 和 `cogt` 的主 PowerShell 配置脚本。
- `Install-CognitoProfile.ps1`: PowerShell 环境安装程序。
- `config.example.json`: 用户配置文件模板。

## 🤖 Cognito Agent 智能代理（阶段 1）

后端现在内置了对自主智能代理的支持，能够安全调用系统和本地工具。

### API 接口
- `POST /api/agent/loop`: 执行“思考-行动”循环的 SSE 事件流接口。
  - **Body 参数**: `{ "messages": [...], "cwd": "path/to/repo", "model_params": {} }`
  - **返回事件**: `text_delta` (文本), `tool_call` (工具调用), `tool_result` (工具结果), `done` (完成), `error` (错误)。

### 会话与持久化（阶段 2）
会话内容以追加写（append-only）的形式保存在 `~/.cognito/sessions/` 的 JSONL 文件中，并通过 `index.json` 进行全局索引管理。

- **自动压缩**: 当会话的历史 Token 数量超过阈值（默认 8000）时，系统会自动生成摘要并对历史记录进行压缩，释放上下文窗口。
- **上下文延续**: 传入 `session_id: "latest"`，系统将自动延续在指定 `cwd` 目录下的最近一次会话。
- **分支克隆 (Forking)**: 支持克隆（Fork）现有会话以探索另一条思考分支，绝不干扰原来的历史对话。

### Python 命令行工具（阶段 3）
提供轻量级 Python 客户端，支持三种工作模式：

- **`print` 模式**（默认）：终端流式输出，配合香农熵（Shannon Entropy）用 TrueColor ANSI 进行字词不确定性着色。
  ```bash
  python -m cli.cognito_cli "解释光合作用" --session-id latest
  ```
- **`json` 模式**：输出格式化的 NDJSON（换行符分割的 JSON），适合与其他 Shell 工具 and 脚本无缝集成。
  ```bash
  python -m cli.cognito_cli "列出工作区文件" --mode json
  ```
- **`rpc` 模式**：通过标准输入输出执行 JSON-RPC 2.0，适合作为长连接后台服务提供进程间调用。
  ```bash
  python -m cli.cognito_cli --mode rpc
  ```

### 内置系统工具
1. `read`：安全读取工作空间（`cwd` 限制）内的文件。
2. `write`：创建或覆盖文件（要求项目处于 `trust` 可信状态）。
3. `edit`：基于块级搜索替换的精准编辑器（要求项目 `trust`）。
4. `bash`：在工作空间中执行无特权的 bash 命令（要求项目 `trust`，禁止 `sudo`）。

### 安全性与受信任边界
- **受保护文件**：关键凭证或身份文件（例如 `auth.js`）在全局保护列表中，严格禁止修改或覆盖。
- **项目受信任声明**：所有写入、编辑、终端执行等破坏性或更改性工具，都必须对工作区启用 `trust` 信任授权。
- **AGENTS.md**：当在 `cwd` 目录下检测到该文件时，系统将自动读取并合并到系统提示词（System Prompt）中，具有最高优先级。

### 扩展插件系统（阶段 4）
支持动态加载 Python 插件扩展功能，完全不需要修改原有后端源码。

- **加载范围**：全局 (`~/.cognito/extensions/`)、配置配置 (`config.json`)、和项目局部 (`.cognito/extensions/`)。
- **插件能力**：注册全新的工具、覆盖默认路由选择、覆盖后端引擎，以及订阅事件（Hook 钩子）。

### 自适应分级升级（阶段 5）
能够评估推理生成中的 Token 不确定性，一旦超过配置阈值，系统会自动拦截并升级到更大参数的高能力模型进行重试。

- **升级阈值**：由环境变量 `COGNITO_ESCALATION_UNCERTAINTY_THRESHOLD` 控制（默认 0.6）。
- **升级路由**：在 `app/services/escalation_routing.py` 中进行精确配置。

## 🧪 测试

测试不确定性功能：
```powershell
# 仅限文本
cog "What is the meaning of life?"

# 语音 + 带有自定义阈值的文本
cogt "Explain quantum entanglement in one sentence." -Threshold 0.4
```

验证向后兼容性（使用不带不确定性的后端）：
```powershell
cog "Test message" -Endpoint "http://external-openai-backend/v1/chat/completions"
```
输出将以标准的白色/灰色文本渲染，不会报错。
