# 审计 04：Docker 安全性
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **网络隔离** | 使用自定义 Docker 网络 (`frontend`, `backend`, `ai`, `monitoring`) 且大多数配置为 `internal: true` 是**极好的安全实践**，限制了服务间的通信。 |
| ✓ | **最小权限 (部分)** | 大多数服务使用 `cap_drop: - ALL` 和 `security_opt: - no-new-privileges:true`，展示了对容器安全原则的扎实理解。 |
| ✗ | **以 Root 身份运行** | 几个关键容器，包括 `ollama` 和基于 NVIDIA 镜像的容器 (`whisper-stt`)，以 **`root` 用户** 身份运行。任何这些应用中的漏洞都会赋予攻击者容器内的管理员权限。 |
| ✗ | **危险的 Linux 能力 (Capabilities)** | 多个服务 (`postgres`, `forgejo`, `duplicati`) 添加了 `DAC_OVERRIDE` 能力。此能力允许进程绕过文件读取、写入和执行权限检查，破坏了文件系统的安全性。 |
| ✗ | **宿主机网络暴露** | `fail2ban` 服务配置了 `network_mode: host`。这**完全破坏了容器的网络隔离**，使其能够直接访问宿主机的网络接口。这是极其危险的，抵消了容器化带来的诸多安全益处。 |
| ✗ | **日志中的机密信息** | `Dockerfile.matrix` 包含一个入口点脚本，该脚本在首次启动时**将生成的机密（macaroon key, form secret 等）打印到容器日志中**。这使得任何有权访问 Docker 日志的人都能获取关键凭据。 |

---

## 2. 详细发现

### ✓ 优点

1.  **应用最小权限原则 (部分)：**
    *   大多数服务配置了 `security_opt: [no-new-privileges:true]`，防止进程获取额外权限。
    *   将 `cap_drop: [ALL]` 作为默认配置，然后仅添加必要的能力 (`cap_add`)，是应当遵循的正确策略。

2.  **稳健的网络隔离：**
    *   网络架构设计得非常好。后端服务无法从外部访问，且通信按功能分段，限制了攻击者的横向移动。

3.  **使用非 Root 用户 (部分)：**
    *   `redis` (`user: "999:999"`)、`authelia` 和 `n8n` (`user: "${PUID:-1000}:${PGID:-1000}"`) 等服务以非特权用户身份正确运行，显著降低了风险。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **DS-01** | **关键** | **`fail2ban` 使用 `network_mode: host`** | 容器拥有对宿主机网络栈的完全访问权限。它可以嗅探所有流量，连接到宿主机上的任何 `localhost` 服务，并干扰宿主机的防火墙规则。该容器被攻破等同于宿主机在网络层面被攻破。 |
| **DS-02** | **关键** | **`matrix-synapse` 日志中暴露机密** | `Dockerfile.matrix` 中的入口点脚本将“生成机密”块打印到标准输出，该输出被 Docker 日志捕获。这使得会话和联邦机密可以轻易被获取。 |
| **DS-03** | **高** | **关键容器中以 `root` 身份运行** | `ollama`、`whisper-stt` 和 `kokoro-tts` 服务以 `root` 身份运行。任何这些服务中的远程代码执行漏洞都会使攻击者获得容器内的完全控制权，具备修改文件、安装恶意软件以及攻击网络上其他服务的能力。 |
| **DS-04** | **高** | **使用 `DAC_OVERRIDE` 能力** | 该能力存在于 `postgres`、`matrix-postgres`、`forgejo` 和 `duplicati` 中，允许进程忽略文件权限。如果攻击者攻破其中一个容器，他们可以读取/写入通常无法访问的文件，可能包括敏感配置文件或其他用户的数据。 |
| **DS-05** | **中** | **不安全地挂载 Docker Socket** | `nginx-proxy` 服务将 Docker socket (`/var/run/docker.sock`) 挂载为“只读”。虽然这很好，但攻破 `nginx-proxy` 仍会允许攻击者获取有关所有其他容器和 Docker 宿主机配置的敏感信息。 |

---

### ⚠️ 警告/建议

1.  **只读文件系统：**
    *   **建议：** 对于不需要在其自身文件系统中写入数据（除了挂载卷之外）的容器，考虑添加 `read_only: true` 选项。这可以缓解许多依赖于编写二进制文件或恶意脚本的攻击。

2.  **安全配置文件 (AppArmor/Seccomp)：**
    *   **建议：** 使用 `apparmor=docker-default` 是一个好的起点。为了获得更高的安全性，可以为每个服务创建自定义的 AppArmor 或 Seccomp 配置文件，限制每个应用可以进行的系统调用。

---

### 🔧 建议的解决方案

1.  **针对 DS-01 (`fail2ban` 使用 `network_mode: host`)：**
    *   **解决方案：** 这是一个难以更改的配置，因为 `fail2ban` 需要修改宿主机的 `iptables`。最安全的方案是**直接在宿主机上运行 `fail2ban`**，而不是在 Docker 中。如果必须保留在容器中，应研究使用更专业、通过工具（如 `nsenter`）受控地在宿主机命名空间中执行命令的容器，而不是暴露整个网络栈。

2.  **针对 DS-02 (Matrix 日志中的机密)：**
    *   **解决方案：** 修改 `Dockerfile.matrix` 中的 `/scripts/entrypoint.sh`，使机密保存到容器内具有受限权限的文件中，而不是将其打印出来。
        ```diff
        --- a/Dockerfile.matrix
        +++ b/Dockerfile.matrix
        @@ -242,15 +242,11 @@

         # Display generated secrets (only on first run)
         if [ ! -f "/data/.secrets_displayed" ]; then
-            echo ""
-            echo "=================================================="
-            echo "GENERATED SECRETS (SAVE THESE!):"
-            echo "=================================================="
-            echo "SYNAPSE_REGISTRATION_SHARED_SECRET=${SYNAPSE_REGISTRATION_SHARED_SECRET}"
-            # ... (remove all other echo statements) ...
-            echo "=================================================="
-            echo ""
+            SECRETS_FILE="/data/generated_secrets.log"
+            echo "Saving generated secrets to ${SECRETS_FILE}" > "${SECRETS_FILE}"
+            echo "SYNAPSE_REGISTRATION_SHARED_SECRET=${SYNAPSE_REGISTRATION_SHARED_SECRET}" >> "${SECRETS_FILE}"
+            # ... (append all other secrets to the file) ...
+            chmod 600 "${SECRETS_FILE}"
             touch /data/.secrets_displayed
         fi
         ```

3.  **针对 DS-03 (以 `root` 身份运行)：**
    *   **针对 `ollama` 的方案：** `ollama` 官方镜像现在支持以非 root 身份运行。应创建一个 `ollama` 用户并确保卷权限（`/root/.ollama` 应改为 `/home/ollama/.ollama`）正确。
    *   **针对自定义 Dockerfile 的方案 (例如 `whisper-stt`)：** 在 Dockerfile 末尾添加以下步骤：
        ```dockerfile
        # 创建非 root 用户
        RUN useradd -ms /bin/bash appuser

        # 确保应用目录权限正确
        RUN chown -R appuser:appuser /app

        # 切换到非 root 用户
        USER appuser

        # 必要时调整命令/入口点
        CMD ["python", "/app/server.py"]
        ```

4.  **针对 DS-04 (`DAC_OVERRIDE`)：**
    *   **解决方案：** 调查每个服务为何需要此能力。通常，它是为了解决挂载卷上的权限问题而添加的。正确的做法是**修复宿主机上的权限**（使用 `setup-permissions.sh` 脚本并确保 `PUID`/`PGID` 匹配），而不是授予危险能力。从所有服务的 `cap_add` 部分删除 `DAC_OVERRIDE`。
