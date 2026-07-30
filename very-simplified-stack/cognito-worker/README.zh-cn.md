# 🛠️ Cognito Worker — 工作空间与 Git 工作树执行服务
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)

本服务 (`cognito-worker`) 是与控制平面 (`cognito-backend`) 进行安全通信的宿主机端（host-side）代码执行与沙箱管理组件。它通过提供安全、隔离的内部 API，负责 Git 工作树（git worktrees）的创建与管理、代码编译与测试运行、代理终端命令执行，并对请求执行 HMAC 密码学签名校验。

## 🚀 主要功能

- **工作树安全隔离**: 使用 `git worktree` 从指定 commit 签出单独的工作目录，避免在自动化分析和修复过程中污染用户的活跃分支。
- **自适应测试验证**: 自动编译代码、运行测试套件，以此客观评估智能代理所提修复补丁（patch）的有效性与稳定性。
- **HMAC 密码学安全校验**: 采用共享密钥机制校验请求签名、Nonce 随机数和时间戳，提供强大的重放攻击防御与数据防篡改保证。
- **Systemd 系统服务支持**: 提供开箱即用的 Systemd 服务配置文件，支持 Linux 宿主机后台持久化运行。

## 🛠️ 安装与运行指南

### 1. 安装系统依赖
确保你的宿主机已安装 Python 虚拟环境与 Git：
```bash
sudo apt-get update
sudo apt-get install -y python3-venv git
```

### 2. 初始化虚拟环境
创建 Python 虚拟环境并安装所需的全部依赖包：
```bash
cd very-simplified-stack/cognito-worker/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 开发环境运行
```bash
# 激活环境并启动服务（默认端口 8001）
source venv/bin/activate
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

### 4. 生产环境部署（使用 Systemd 服务）
如需在后台稳定、持久地运行服务：

1. 根据需要修改 `cognito-worker.service` 文件中的虚拟环境路径。
2. 将服务配置文件复制到 Systemd 目录：
   ```bash
   sudo cp cognito-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```
3. 启动并激活服务：
   ```bash
   sudo systemctl start cognito-worker
   sudo systemctl enable cognito-worker
   ```
4. 查看服务运行状态：
   ```bash
   sudo systemctl status cognito-worker
   ```

## ⚙️ 环境变量配置

支持通过标准环境变量参数自定义运行配置：

- `COGNITO_WORKER_PORT`: 服务的网络监听端口（默认: `8001`）。
- `COGNITO_WORKER_SECRET`: 与控制端（backend）共享的 HMAC 密钥。
- `ALLOWED_ROOTS`: 允许在宿主机上创建 git worktree 的根目录白名单。
- `WORKER_ID`: 唯一的 Worker 实例标识符。

## 🧪 单元测试

在本地执行 Worker 测试套件：
```bash
source venv/bin/activate
PYTHONPATH=. pytest tests/
```
