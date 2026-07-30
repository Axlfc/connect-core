# 🛠️ Cognito Worker — Workspace & Git Worktree Execution Service
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)

This service (`cognito-worker`) is the host-side execution component communicating with the control plane (`cognito-backend`). It provides a secure, isolated internal API for workspace sandboxing (using git worktrees), executing code compilation/tests, processing agent terminal commands, and validating cryptographically signed requests.

## 🚀 Key Features

- **Worktree Management**: Isolates changes on custom commits using `git worktree` to prevent active-branch collision during scanning and remediation.
- **Intelligent Verification**: Automates code compiling and testing to verify proposed agent patches and changes.
- **HMAC Cryptographic Validation**: Validates incoming signatures using shared secrets, preventing request tampering and replay attacks.
- **Systemd Integration**: Service file included for easy deployment in persistent Linux backgrounds.

## 🛠️ Installation & Bootstrapping

### 1. System Dependencies
Verify that Python and Git are installed on your host:
```bash
sudo apt-get update
sudo apt-get install -y python3-venv git
```

### 2. Virtual Environment
Setup a virtual environment and install dependency requirements:
```bash
cd very-simplified-stack/cognito-worker/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Directly (Development)
```bash
# Start worker app on port 8001
source venv/bin/activate
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

### 4. Running as Systemd Service (Production)
For persistent background execution:

1. Customize target paths inside `cognito-worker.service` if needed.
2. Copy the service unit to systemd directory:
   ```bash
   sudo cp cognito-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```
3. Start and enable systemd daemon:
   ```bash
   sudo systemctl start cognito-worker
   sudo systemctl enable cognito-worker
   ```
4. Verify daemon health status:
   ```bash
   sudo systemctl status cognito-worker
   ```

## ⚙️ Configuration (Environment Variables)

Customize behavior using standard env variables:

- `COGNITO_WORKER_PORT`: Network port for listening socket (default: `8001`).
- `COGNITO_WORKER_SECRET`: HMAC key shared with control plane to authenticate requests.
- `ALLOWED_ROOTS`: List of directory roots on the host allowed for git worktrees.
- `WORKER_ID`: Unique unifed worker ID.

## 🧪 Testing

To execute worker-specific test suites:
```bash
source venv/bin/activate
PYTHONPATH=. pytest tests/
```
