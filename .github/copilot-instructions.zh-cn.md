# connect-core - GitHub Copilot 指令
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/.github/copilot-instructions.ca.md)


## 项目摘要

**connect-core** 是一个集成了以下组件的 AI 自动化平台：
- **n8n**: 工作流编排器
- **Ollama**: 本地 LLM 模型
- **Whisper**: 语音转文本 (STT)
- **Kokoro**: 文本转语音 (TTS)
- **Qdrant**: 向量数据库
- **Matrix**: 联邦消息传递
- **Forgejo**: Git 托管

## 服务架构

### 核心服务（始终活动）
```
PostgreSQL → 主数据库
    ↓
Redis → 缓存和会话
    ↓
Qdrant → 向量嵌入 (Embeddings)
    ↓
Ollama → LLM 推理
    ↓
n8n → 工作流编排
```

### 语音服务（配置文件：voice）
```
Whisper STT ← 音频输入
    ↓
n8n 工作流
    ↓
Kokoro TTS → 音频输出
```

### 可选服务
- **Monitoring**: Prometheus + Grafana + Loki
- **Zrok**: 安全公共隧道
- **ComfyUI**: 图像生成

---

## 关键命令

### 首次初始化（必须执行）

```bash
# 1. 生成机密信息 (Secrets)（仅需执行一次）
./scripts/generate-secrets.sh

# 2. 构建自定义镜像（务必首先执行）
docker compose --profile gpu-nvidia --profile voice build

# 3. 验证构建结果
docker images | grep local/

# 4. 启动服务
docker compose --profile gpu-nvidia --profile voice up -d

# 5. 验证状态
docker compose ps
docker compose logs -f n8n
```

### 日常开发

```bash
# 查看某个服务的日志
docker compose logs -f [service]

# 重启某个服务
docker compose restart [service]

# 修改 Dockerfile 后重新构建
docker compose build --no-cache [service]
docker compose up -d [service]

# 停止所有服务
docker compose down

# 停止并清理卷（危险：会删除数据）
docker compose down -v
```

### 可用配置文件 (Profiles)

```bash
# NVIDIA GPU + 语音服务
docker compose --profile gpu-nvidia --profile voice up -d

# 仅 CPU（无 GPU）
docker compose --profile cpu --profile voice-cpu up -d

# AMD GPU
docker compose --profile gpu-amd up -d

# 带监控功能
docker compose --profile gpu-nvidia --profile voice --profile monitoring up -d

# 带 Zrok 隧道
docker compose --profile gpu-nvidia --profile voice --profile zrok up -d
```

---

## 一致性规则

### 修改 docker-compose.yml 时

1. **带有 `build:` 的服务** 始终需要：
   ```yaml
   build:
     context: .
     dockerfile: Dockerfile.service
   image: local/service:tag
   pull_policy: build  # 可选但推荐
   ```

2. **使用 GPU 的服务** 始终需要：
   ```yaml
   profiles: ["gpu-nvidia"]
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```

3. **使用机密信息的服务** 始终需要：
   ```yaml
   secrets:
     - secret_name
   environment:
     - VARIABLE_FILE=/run/secrets/secret_name
   ```

### 创建新服务时

1. 为关键服务**添加健康检查 (Healthcheck)**
2. 通过 `deploy.resources.limits` **限制资源**
3. 为非公共服务**使用内部网络** (`backend`, `ai`)
4. **添加结构化日志** (带有轮转功能的 json-file)
5. **应用安全增强**:
   ```yaml
   security_opt:
     - no-new-privileges:true
   cap_drop:
     - ALL
   cap_add:
     - [仅必要的 CAPABILITIES]
   ```

---

## 快速故障排除

| 错误 | 原因 | 解决方案 |
|-------|-------|----------|
| `pull access denied for local/*` | 镜像未构建 | 首先运行 `docker compose build` |
| `failed to resolve source metadata` | 基础镜像不存在 | 在 Docker Hub 上核实版本 |
| 健康检查中 `connection refused` | 服务未启动 | 检查日志：`docker compose logs [service]` |
| `secret not found` | `./secrets/` 中的文件缺失 | 运行 `./scripts/generate-secrets.sh` |
| 未检测到 GPU | 未安装 NVIDIA 驱动 | 安装 `nvidia-container-toolkit` |

---

## 解决方案模式

### 问题：服务无法启动

```bash
# 1. 查看完整日志
docker compose logs [service] --tail=100

# 2. 验证依赖项
docker compose ps | grep -E 'postgres|redis|qdrant'

# 3. 验证机密信息
ls -la secrets/

# 4. 进入容器进行调试
docker compose exec [service] /bin/sh
```

### 问题：卷权限错误

```bash
# 1. 验证所有权
docker compose exec [service] ls -la /path/to/volume

# 2. 修复权限（如有必要）
sudo chown -R $(id -u):$(id -g) ./volumes/[service]
```

### 问题：未检测到 GPU

```bash
# 1. 验证驱动程序
nvidia-smi

# 2. 验证 Docker 运行时
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi

# 3. 如果失败，请重新安装 nvidia-container-toolkit
```

---

## 关键环境变量

### 强制性（在 .env 中）

```bash
# 数据库
POSTGRES_USER=n8n_user
POSTGRES_PASSWORD=<已生成>
POSTGRES_DB=n8n_db

# n8n
N8N_ENCRYPTION_KEY=<已生成>
N8N_RUNNERS_AUTH_TOKEN=<已生成>
WEBHOOK_URL=https://n8n.your-domain.com

# 域名（用于 nginx-proxy）
N8N_DOMAIN=n8n.localhost
OLLAMA_DOMAIN=ollama.localhost
FORGEJO_DOMAIN=forgejo.localhost
```

### 可选

```bash
# Ollama 模型（启动时下载）
OLLAMA_MODEL_1=llama3:8b
OLLAMA_MODEL_2=nomic-embed-text

# Whisper 模型
ASR_MODEL=base.en

# 监控
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<已生成>
```

---

## 快速参考

- **完整文档**: `./docs/README.md`
- **高级故障排除**: `./docs/WHISPER_TROUBLESHOOTING.md`
- **有用脚本**: `./scripts/`
- **配置文件**: `./config/`
- **日志**: `./logs/[service]/`

---

## 基础镜像版本验证

### ⚠️ 已知问题：基础镜像过时

**问题：** 如果发生以下情况，Dockerfile 中的基础镜像版本可能不可用：
- 指定了未来版本（例如：现在是 `24.12`，却指定了 `25.01`）
- 镜像从公共注册表中被移除
- 标签 (Tags) 被重命名或弃用

**构建前的快速修复：**

```bash
# 查看使用了哪些镜像
grep -h "^FROM " Dockerfile* | sort -u

# 如果出现 "not found" 错误，请更新版本并重试
docker compose build --no-cache
```

**已知稳定版本 (2026年1月):**
- `nvcr.io/nvidia/pytorch:24.12-py3` ✅
- `ollama/ollama:0.2.1` ✅
- `qdrant/qdrant:v1.9.2` ✅
- `python:3.11-slim` (用于 LibreTranslate，通过 pip 安装) ✅
- `erikvl87/languagetool:6.4` ✅

**有问题的版本:**
- `nvcr.io/nvidia/pytorch:25.01-py3` ❌ 不存在（未来版本）
- `libretranslate/libretranslate:1.6.1` ❌ 未找到
- `libretranslate/libretranslate:1.5.0` ❌ 未找到（官方镜像已被移除）

**针对 LibreTranslate 实施的解决方案:**
- 切换到 `python:3.11-slim` + `pip install libretranslate`
- 更可靠且自动维护
- 参见 [docs/LIBRETRANSLATE_TROUBLESHOOTING.md](../docs/LIBRETRANSLATE_TROUBLESHOOTING.md)

**如果遇到 "failed to resolve source metadata" 错误:**
```bash
# 1. 在 Docker Hub 上验证可用版本
# 镜像示例：https://hub.docker.com/r/name/image/tags

# 2. 更新 Dockerfile（如果适用）
sed -i 's/OLD_VERSION/NEW_VERSION/g' Dockerfile.service

# 3. 重新构建
docker compose build --no-cache [service]
```

---

## GitHub Copilot 注意事项

- 在启动使用 `local/*` 镜像的服务前，**务必先进行构建**
- **配置文件是互斥的**：使用 `gpu-nvidia` 或 `cpu`，不要同时使用两者
- **机密信息是文件**，而不是直接的环境变量
- **健康检查有 `start_period`**：在诊断故障前请先等待
- **命名卷 (Named volumes)** 在重启之间持久存在，**绑定挂载 (Bind mounts)** 反映即时更改
- **镜像版本**：始终使用 LTS/稳定版本，不要使用未来版本
- **LibreTranslate**: 使用 Python + pip 而不是官方 Docker 镜像（更可靠）
