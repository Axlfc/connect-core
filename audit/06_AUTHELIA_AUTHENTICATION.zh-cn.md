# 审计 06：AUTHELIA - 身份验证与授权
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **集成与 SSO** | Authelia 作为 Nginx 的 `forward auth` 提供程序的配置已**正确实现**。单点登录 (SSO) 流程在概念上是稳健的。 |
| ✓ | **访问策略** | `default_policy: deny` 策略是**最佳安全实践**，强制每个服务都必须经过显式授权。基于域名的规则清晰且易于管理。 |
| ✗ | **密码策略 (哈希)** | `argon2id` 哈希算法的配置**极其薄弱**，仅使用了 `iterations: 1`。这使得存储的密码哈希容易受到高速离线破解攻击。 |
| ✗ | **会话安全性** | 会话 Cookie 配置为 `secure: false`，这是一个**仅限开发**的参数。在生产环境中，这将允许会话 Cookie 通过 HTTP 以明文形式传输，使其面临会话劫持 (Session Hijacking) 攻击。 |
| ⚠️ | **存储后端** | 系统使用本地 SQLite 数据库进行存储。虽然可用，但不建议用于高并发或需要高可用性的生产环境。 |
| ⚠️ | **机密管理** | `admin` 用户密码从环境变量 (`AUTHELIA_ADMIN_PASSWORD`) 加载，这延续了在 **审计 02** 中确定的不一致且安全性较低的机密管理策略。 |

---

## 2. 详细发现

### ✓ 优点

1.  **零信任 (Zero Trust) 模型：**
    *   `access_control.default_policy: deny` 策略非常出色。它确保了没有任何新服务会在没有显式授权规则的情况下被意外暴露。

2.  **防暴力破解保护：**
    *   `regulation` 章节配置了合理的值（`max_retries: 3`, `ban_time: 15m`）。这为防御在线密码猜测攻击提供了有效的第一道防线。

3.  **会话机密管理：**
    *   Authelia 会话和 JWT 机密通过 Docker Secrets 正确管理 (`AUTHELIA_SESSION_SECRET_FILE`, `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE`)，这是处理此类凭据最安全的方式。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **A-01** | **关键** | **薄弱的密码哈希** | `argon2id` 的 `password.iterations: 1` 设置低得危险。Argon2id 旨在通过高计算强度来保证安全。如果只进行 1 次迭代，获取了 `users_database.yml` 文件的攻击者破解密码的速度将比预期快数千倍，使得恢复弱密码变得轻而易举。 |
| **A-02** | **关键** | **不安全的会话 Cookie** | `cookies.secure: false` 配置告知浏览器可以通过未加密的 HTTP 连接发送会话 Cookie。如果由于某种原因（例如 `sslstrip` 攻击）用户通过 HTTP 连接，其会话 Cookie 就会被拦截，允许攻击者完全控制其账户。 |
| **A-03** | **中** | **“记住我”时长过长** | `remember_me_duration` 设置为 `1y`（一年）。如果用户的会话被攻破，即使该用户没有主动登录，攻击者也有可能在长达一年的时间内拥有访问权限。 |

---

### ⚠️ 警告/建议

1.  **生产环境后端：**
    *   **建议：** 对于生产环境，将 Authelia 的 `storage`（存储）从 SQLite 迁移到更稳健的数据库（如 PostgreSQL）。这能提高性能、并发能力和可靠性。Authelia 可以使用堆栈中已有的同一个 Postgres 实例（使用独立的数据库）。

2.  **Authelia 文档：**
    *   项目包含多个 `AUTHELIA_*.md` 文件。将它们整合到 `/docs` 或 `/audit` 目录下的单一指南中，以阐明身份验证架构和设计决策，将大有裨益。

---

### 🔧 建议的解决方案

1.  **针对 A-01（加强哈希 - 关键）：**
    *   **解决方案：** 将 `authelia/configuration.yml` 中的迭代次数增加到安全值。Authelia 推荐值为 `2`，但 `3` 或 `4` 能在安全性和性能之间提供更好的平衡。
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -60,7 +60,7 @@
     path: /config/users_database.yml
     password:
       algorithm: argon2id
-      iterations: 1
+      iterations: 3
       salt_length: 16
       parallelism: 8
       memory: 64
        ```
    *   **重要提示：** 应用此更改后，所有现有的用户密码都必须重置，以便使用新配置重新进行哈希处理。

2.  **针对 A-02（保护会话 Cookie - 关键）：**
    *   **解决方案：** 在 Cookie 配置中将 `secure` 的值更改为 `true`。在部署到使用 HTTPS 的环境之前，必须完成此操作。
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -40,7 +40,7 @@
       authelia_url: https://auth.localhost
       default_redirection_url: https://forgejo.localhost
       same_site: Lax
-      secure: false  # 在带 HTTPS 的生产环境中设置为 true
+      secure: true
        ```

3.  **针对 A-03（缩短会话时长）：**
    *   **解决方案：** 将 `remember_me_duration` 缩短到更保守的期限，例如 `1M`（一个月）或 `14d`（两周），以限制会话被攻破时的暴露窗口。
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -32,7 +32,7 @@
   # session.secret 通过 AUTHELIA_SESSION_SECRET_FILE 提供
   expiration: 1h
   inactivity: 5m
-  remember_me_duration: 1y
+  remember_me_duration: 30d
   # 针对使用 .localhost 域名的本地开发的每个 Cookie 配置
   cookies:
     - name: authelia_session
        ```
