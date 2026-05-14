# 审计 02：环境变量与配置管理
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **机密生成** | 初始化脚本 (`init_env.sh`) 使用加密安全的方法 (`openssl rand`) 生成机密 (Secrets)，这是一种极好的做法。 |
| ✓ | **文件保护** | `.gitignore` 文件已正确配置，排除了 `secrets/` 和 `.env*`，防止凭据意外暴露在仓库中。 |
| ⚠️ | **混合方法** | 项目同时使用两种方法管理机密：**Docker Secrets**（安全）和**通过 `.env` 的环境变量**（安全性较低）。这种不一致是主要的风险来源。 |
| ✗ | **潜在暴露** | `POSTGRES_PASSWORD` 和 `REDIS_PASSWORD` 等关键机密被作为环境变量注入容器，这使得它们可以通过 `docker inspect`、日志以及可能的监控工具被看到。 |
| ✗ | **输入验证** | Shell 脚本虽然稳健，但在交互模式下未对用户输入进行详尽验证，这可能允许在 `.env` 文件中注入恶意字符。 |

---

## 2. 详细发现

### ✓ 优点

1.  **安全的机密生成：**
    *   `init_env.sh` 脚本将 `openssl rand` 作为创建密码和密钥的主要方法。这是生成安全随机值的行业最佳实践。

2.  **`.env.example` 文件处理：**
    *   `generate_env_example.sh` 脚本非常智能。它通过模式（`PASSWORD`, `KEY`, `TOKEN` 等）识别敏感变量并将其清空，同时保留非敏感的配置值。这确保了示例文件既安全又有用。

3.  **部分使用 Docker Secrets：**
    *   `docker-compose.yml` 定义了 `secrets:` 块，并在多个服务（例如 `authelia`, `n8n-import`）中正确使用了它们。这展示了对 Docker 中处理机密正确方式的了解。
    *   **示例（`authelia` 服务）：**
        ```yaml
        secrets:
          - authelia_jwt_secret
          - authelia_session_secret
        environment:
          - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
          - AUTHELIA_SESSION_SECRET_FILE=/run/secrets/authelia_session_secret
        ```
    *   这种方法是安全的，因为机密以文件形式挂载到容器内的 `/run/secrets/` 中，且绝不会作为环境变量暴露。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **C-01** | **高** | **关键机密使用环境变量** | `postgres` 和 `redis` 主服务通过从 `.env` 文件加载的环境变量接收密码。拥有 Docker 宿主机访问权限的攻击者可以使用 `docker inspect postgres` 命令提取这些凭据。 |
| **C-02** | **中** | **机密管理不一致** | 项目对某些服务（Authelia）使用 Docker Secrets，但对其他服务（Postgres, Redis）使用环境变量。缺乏统一标准增加了复杂性、人为错误风险以及攻击面。 |
| **C-03** | **低** | **控制台显示机密** | `init_env.sh` 在控制台中显示生成的机密的一部分。虽然是截断的，但这可能会将机密暴露给 Shell 历史记录 (`.bash_history`) 或旁观者。 |

---

### ⚠️ 警告/建议

1.  **`ENV_MANAGEMENT.md` 文档：**
    *   `ENV_MANAGEMENT.md` 文件虽然存在，但可以更明确地说明机密策略。它应该解释*为什么*首选 Docker Secrets，并警告对敏感数据使用环境变量的风险。

2.  **Shell 脚本增强 (Hardening)：**
    *   `init_env.sh` 和 `generate_env_example.sh` 脚本较为复杂。一个好的做法是在开头添加 `set -o pipefail`，以确保如果中间命令失败，流水线也会失败。

---

### 🔧 建议的解决方案

1.  **针对 C-01 和 C-02（统一使用 Docker Secrets - 关键）：**
    *   **第 1 步：修改 `docker-compose.yml`：**
        *   重新配置目前为机密使用环境变量的所有服务，改用 Docker Secrets。
        *   **`postgres` 服务示例：**
            ```diff
            --- a/docker-compose.yml
            +++ b/docker-compose.yml
            @@ -143,8 +143,10 @@
             restart: unless-stopped
             ports:
               - "127.0.0.1:5432:5432"
-            environment:
-              - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
+            secrets:
+              - postgres_password
+            environment:
+              - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
               - POSTGRES_USER=${POSTGRES_USER}
               - POSTGRES_DB=${POSTGRES_DB}
               - PGDATA=/var/lib/postgresql/data/pgdata
            ```
    *   **第 2 步：更新 `init_env.sh`：**
        *   修改脚本，不再将 `POSTGRES_PASSWORD=机密值` 写入 `.env`，而是在 `secrets/` 目录中创建相应文件。
            ```bash
            # 在 init_env.sh 中，代替 sed 操作：
            echo "$new_value" > secrets/postgres_password.txt
            chmod 600 secrets/postgres_password.txt
            # 并在 .env 中删除该变量
            sed -i '/^POSTGRES_PASSWORD=/d' "$TARGET_FILE"
            ```
        *   这将所有机密集中到一个位置 (`/secrets`)，并使用正确的权限进行管理。

2.  **针对 C-03（显示机密）：**
    *   **解决方案：** 修改 `init_env.sh`，不在控制台中显示生成的值。只需告知用户值已生成并保存。
        ```diff
        --- a/init_env.sh
        +++ b/init_env.sh
        @@ -145,7 +145,7 @@
             echo ""
             echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
             echo -e "${BLUE}变量：${NC} $var"
-            echo -e "${BLUE}生成的值：${NC} ${new_value:0:20}...${new_value: -10}"
+            echo -e "${BLUE}生成的值：${NC} [出于安全原因已隐藏]"
             echo -n "是否使用此值？(Y/n/自定义): "
             read -r response
         ```
