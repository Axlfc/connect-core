# 审计 05：反向代理与 NGINX
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **Authelia 集成** | 与 Authelia 集成的 `forward auth` 配置是**正确且安全**的。使用 `internal` 块和正确的请求头传输 (`X-Forwarded-*`) 遵循了最佳实践。 |
| ✓ | **配置结构** | 使用 `vhost.d` 应用各服务保护的配置结构是**模块化且可扩展**的，允许对受保护的端点进行细粒度控制。 |
| ✗ | **缺少安全响应头** | Nginx 配置**完全缺少显式的安全响应头 (Security Headers)**。未配置 HSTS、CSP、X-Frame-Options、Permissions-Policy 以及其他对代理进行“加固”所必需的响应头。 |
| ✗ | **SSL/TLS 配置薄弱** | 未指定 SSL/TLS 策略。这意味着依赖于 `nginx-proxy` 的默认值，这可能允许使用弱加密套件或过时的 TLS 版本，使通信面临潜在的降级攻击。 |
| ⚠️ | **未设置频率限制** | 在反向代理层面没有任何 `rate limiting`（频率限制）配置。这使得后端服务容易受到拒绝服务 (DoS) 攻击或可能耗尽资源的暴力破解尝试。 |

---

## 2. 详细发现

### ✓ 优点

1.  **Forward Auth 的实现：**
    *   `nginx-proxy/authelia-location.conf` 文件配置完美。它使用 `internal` 指令防止从外部访问验证端点，并正确传递了 Authelia 做出授权决策所需的所有请求头。
    *   `vhost.d` 中的文件（如 `n8n.localhost`）包含了此配置块并正确配置了 `auth_request` 指令，确保拦截未经身份验证的请求。

2.  **配置的模块化：**
    *   `vhost.d` 系统允许有选择地应用身份验证。这非常灵活，例如，如果需要，可以让某些端点（如 webhooks）保持不受保护状态，而不影响应用其余部分的安全性。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **RP-01** | **高** | **缺少关键安全响应头** | 如果没有 HSTS (`Strict-Transport-Security`)，浏览器就不会强制使用 HTTPS，从而为 `sslstrip` 攻击留下隐患。没有 `X-Frame-Options` 或 `Content-Security-Policy: frame-ancestors`，站点容易受到*点击劫持 (Clickjacking)* 攻击。缺少稳健的 CSP 会导致跨站脚本 (XSS) 攻击。 |
| **RP-02** | **中** | **依赖默认 SSL/TLS 配置** | 未显式定义允许的 TLS 协议和加密套件，可能会导致服务器在客户端请求时协商使用弱算法或不安全的算法进行连接。 |
| **RP-03** | **中** | **边缘侧缺少频率限制** | 如果没有 `rate limiting`，攻击者可以向后端服务发送无限数量的请求，尝试猜测凭据、寻找漏洞或仅仅是为了耗尽服务器资源（CPU、内存、数据库连接）。 |

### ⚠️ 警告/建议

1.  **压缩：**
    *   未观察到显式的压缩配置 (Gzip/Brotli)。启用压缩可以显著提高终端用户的加载速度。

2.  **自定义日志：**
    *   Nginx 日志格式采用标准格式。可以对其进行自定义，以包含更多对调试和安全分析有用的信息，例如 `upstream` 响应时间或 Authelia 的 `headers`。

### 🔧 建议的解决方案

1.  **针对 RP-01 和 RP-02（添加响应头和 SSL/TLS 加固）：**
    *   **解决方案：** 创建一个新的全局配置文件，例如 `nginx-proxy/conf.d/hardening.conf`，并添加以下指令。这将向代理后的所有服务应用稳固的安全策略。
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf

        # --- SSL/TLS 加固 ---
        # 强制使用 TLS 1.2 和 1.3，以及现代且安全的加密套件。
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;

        # --- 安全响应头 ---
        # 强制 HTTPS 1 年，包括子域名。
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        # 防止点击劫持。
        add_header X-Frame-Options "SAMEORIGIN" always;

        # 防止浏览器推测 MIME 类型。
        add_header X-Content-Type-Options "nosniff" always;

        # 启用浏览器的 XSS 过滤器。
        add_header X-XSS-Protection "1; mode=block" always;

        # 控制在 Referer 请求头中发送哪些信息。
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # (可选但推荐) 内容安全策略 (CSP) - 需要微调！
        # 这是一个严格的策略，如果引起问题，请从较宽松的策略开始。
        # add_header Content-Security-Policy "default-src 'self'; script-src 'self'; img-src 'self'; style-src 'self'; object-src 'none';" always;
        ```

2.  **针对 RP-03（实施频率限制）：**
    *   **解决方案：** 在同一个 `hardening.conf` 文件中添加 `limit_req_zone` 配置，以建立全局限制。
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf (续)

        # --- 频率限制 ---
        # 定义一个内存区域来跟踪 IP。10m 可以存储约 160,000 个 IP。
        limit_req_zone $binary_remote_addr zone=global_limit:10m rate=10r/s;

        # 将限制应用于所有位置。
        limit_req zone=global_limit burst=20 nodelay;
        ```
        *   **注意：** 此配置将每个 IP 限制为每秒 10 个请求，允许 20 个请求的突发 (burst)。这些值只是一个起点，应根据应用的预期流量进行调整。
