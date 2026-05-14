# Authelia 配置 - 常见问题解答与您的疑问
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/AUTHELIA_FAQ.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/AUTHELIA_FAQ.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/AUTHELIA_FAQ.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/AUTHELIA_FAQ.ca.md)


## Q1: SMTP 配置 - 配置 SMTP 的正确方式是什么？

### 您的疑问
"在新的格式中，配置 SMTP 的正确方式是什么？我们是否应该使用 `notifier.smtp.address` 而不是单独的 `host` 和 `port`？"

### 解答：是的，仅使用 `address` 格式

**正确方式 (现代版本 v4.38.0+)**:
```yaml
notifier:
  smtp:
    address: 'smtp://smtp.tinet.cat:587'
    timeout: 5s
    sender: 'Authelia <noreply@example.com>'
    tls:
      server_name: smtp.tinet.cat
      skip_verify: false
```

**格式**: `smtp[s]://[user@]host[:port]`

**示例**:
```
smtp://smtp.example.com:587              # 端口 587 上的 STARTTLS
smtps://smtp.example.com:465             # 端口 465 上的隐式 TLS
smtp://user@smtp.example.com:587         # 在 URL 中包含用户
```

**通过环境变量配置凭据**:
```yaml
environment:
  - AUTHELIA_NOTIFIER_SMTP_ADDRESS=smtp://smtp.tinet.cat:587
  - AUTHELIA_NOTIFIER_SMTP_USERNAME=your_email@example.com
  - AUTHELIA_NOTIFIER_SMTP_PASSWORD=your_password
  - AUTHELIA_NOTIFIER_SMTP_SENDER=Authelia <noreply@example.com>
```

**从 `.env` 文件配置**:
```bash
SMTP_HOST=smtp.tinet.cat
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_password
SMTP_SENDER=Authelia <noreply@example.com>
```

**不要混合使用格式** (会导致冲突):
```yaml
# ❌ 错误 - 这会导致冲突错误：
notifier:
  smtp:
    host: smtp.example.com        # ❌ 旧格式
    port: 587                      # ❌ 旧格式
    address: 'smtp://...:587'      # ❌ 新格式 (冲突!)
```

---

## Q2: Localhost 的会话 Cookie

### 您的疑问
"对于使用 `.localhost` 域名的本地开发，我们应该如何配置会话 Cookie？错误提示域名必须包含点号或是一个 IP 地址。"

### 解答：在配置中使用 `localhost`，nginx-proxy 会处理浏览器兼容性

**配置内容**:
```yaml
session:
  cookies:
    - name: authelia_session
      domain: localhost              # ✅ 适用于 Docker 网络
      authelia_url: https://auth.localhost
      default_redirection_url: https://forgejo.localhost
      same_site: Lax
      secure: false                  # 在生产环境中更改为 true
```

**工作原理**:
1. **Docker 网络**: 服务之间使用 `localhost` 通信 (运行良好)
2. **浏览器访问**: 用户访问 `http://auth.localhost:9091`
3. **nginx-proxy**: 拦截对 `auth.localhost` 的请求并将其转发给 Authelia
4. **Cookie 域名**: nginx-proxy 会处理 Cookie 重写以实现浏览器兼容性
5. **结果**: 浏览器永远不会直接看到无效的 `localhost` 域名

**为什么这样可行**:
- Docker 内部 DNS 会在容器内解析 `localhost`
- 浏览器永远不会直接在 `localhost` 域名上设置 Cookie
- nginx-proxy 作为中间层管理 Cookie 域名的转换
- Docker 内部访问和浏览器访问都能完美运行

**不应该做的**:
```yaml
# ❌ 错误 - 这也会失败：
domain: .localhost    # 浏览器仍然拒绝单标签域名

# ❌ 错误 - 对于开发来说限制太严：
domain: auth.localhost  # 仅适用于 auth.localhost，不适用于其他服务

# ✅ 正确:
domain: localhost     # 适用于 Docker 网络 + nginx-proxy 管理浏览器
```

**环境变量**:
```yaml
environment:
  - VIRTUAL_HOST=${AUTHELIA_DOMAIN:-auth.localhost}
  - VIRTUAL_PORT=9091
```

**在 `.env` 中**:
```bash
AUTHELIA_DOMAIN=auth.localhost
```

---

## Q3: JWT 密钥迁移

### 您的疑问
"我们是否应该更新配置文件以使用新的 `identity_validation.reset_password.jwt_secret` 键？"

### 解答：是的，请迁移到新的键路径

**旧方式 (已废弃)**:
```yaml
jwt_secret: your_secret_here
```

**新方式 (v4.38.0+)**:
```yaml
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
      # 密钥通过环境变量注入
```

**环境变量**:
```yaml
environment:
  - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**Docker Compose 配置**:
```yaml
secrets:
  - authelia_jwt_secret

services:
  authelia:
    environment:
      - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**为什么要迁移？**:
- ✅ 支持 Authelia 新的密码重置流程
- ✅ 遵循语义化版本控制 (针对不同用途使用独立的 JWT)
- ✅ 允许未来将身份验证与密码重置的 JWT 分离
- ✅ 消除废弃警告

**向后兼容性**:
- Authelia 4.38.0+ 仍然接受旧的 `jwt_secret` 但会显示警告
- 为了获得整洁的日志，需要使用新配置
- 密码重置功能仅在使用新密钥时有效

---

## Q4: 默认重定向 URL 配置

### 您的疑问
"我们应该如何在每个 Cookie 级别正确配置 `default_redirection_url`，而不是进行全局配置？"

### 解答：将其移动到每个 Cookie 的配置内部

**旧方式 (会导致错误)**:
```yaml
session:
  expiration: 1h
  default_redirection_url: https://forgejo.localhost  # ❌ 错误
  cookies:
    - name: authelia_session
      domain: localhost
```

**新方式 (正确)**:
```yaml
session:
  expiration: 1h
  # 不要放在这里 ❌

  cookies:
    - name: authelia_session
      domain: localhost
      default_redirection_url: https://forgejo.localhost  # ✅ 在这里
      authelia_url: https://auth.localhost
      same_site: Lax
      secure: false

# 可选：根级别的全局备选方案
default_redirection_url: 'https://forgejo.localhost'
```

**多个 Cookie (进阶)**:
```yaml
session:
  cookies:
    # 生产环境 Cookie
    - name: authelia_session
      domain: example.com
      default_redirection_url: https://app.example.com
      secure: true

    # 开发环境 Cookie
    - name: authelia_session_dev
      domain: localhost
      default_redirection_url: https://forgejo.localhost
      secure: false

# 全局备选方案
default_redirection_url: 'https://example.com'
```

**工作原理**:
1. 用户访问受保护的服务 (例如 n8n.localhost)
2. 被重定向到 Authelia 登录页面 (auth.localhost)
3. 登录后，Authelia 会检查每个 Cookie 的 `default_redirection_url`
4. 重定向到配置的 URL (例如 forgejo.localhost)
5. 如果没有设置每个 Cookie 的配置，则使用全局 `default_redirection_url`

**必填配置字段**:
```yaml
cookies:
  - name: authelia_session              # Cookie 名称
    domain: localhost                   # Cookie 域名
    authelia_url: https://auth.localhost  # Authelia 端点
    default_redirection_url: https://forgejo.localhost  # 备选目标
    same_site: Lax                      # CSRF 保护
    secure: false                       # 生产环境为 true
```

---

## Q5: HTTP vs HTTPS - 本地开发 vs 生产环境

### 您的疑问
"我们可以在本地开发中使用 HTTP 运行 Authelia (由 nginx-proxy 通过自签名证书管理 SSL 或不使用 SSL)，然后在生产环境中切换到 HTTPS 吗？"

### 解答：是的，Authelia 与协议无关

**本地开发 (HTTP，无 SSL)**:
```yaml
# 在 authelia/configuration.yml 中:
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ 仅使用 HTTP

session:
  cookies:
    - name: authelia_session
      secure: false         # ✅ 允许 HTTP Cookie
      same_site: Lax
```

**Docker Compose**:
```yaml
authelia:
  expose:
    - 9091
  environment:
    - VIRTUAL_HOST=auth.localhost
    - VIRTUAL_PORT=9091
    # nginx-proxy 通过 HTTP 提供服务
```

**如何访问**:
```
浏览器访问: http://auth.localhost:9091
浏览器访问: http://n8n.localhost
```

---

**生产环境 (带有 Let's Encrypt 的 HTTPS)**:
```yaml
# 在 authelia/configuration.yml 中 (无需更改):
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ 仍为 false
    # 由 nginx-proxy 处理 TLS 终止

session:
  cookies:
    - name: authelia_session
      secure: true          # ✅ 要求 HTTPS
      same_site: Strict
```

**Docker Compose**:
```yaml
authelia:
  expose:
    - 9091
  labels:
    - com.github.jrcs.letsencrypt_nginx_proxy_companion.enable=true
  environment:
    - VIRTUAL_HOST=auth.example.com
    - VIRTUAL_PORT=9091
    # nginx-proxy + acme-companion 处理 HTTPS + Let's Encrypt
```

**如何访问**:
```
浏览器访问: https://auth.example.com
浏览器访问: https://app.example.com
```

---

**关键点**:

1. **Authelia 本身**: 内部始终运行在 HTTP (端口 9091) 上
2. **TLS 终止**: 让 nginx-proxy 处理 HTTPS 终止
3. **Authelia 配置**: 在所有场景下 `tls.enabled: false`
4. **会话安全**:
   - 本地开发: `secure: false` (允许 HTTP)
   - 生产环境: `secure: true` (要求 HTTPS)
5. **迁移路径**:
   - 从本地开发开始 (HTTP，无 SSL)
   - 迁移到生产环境 (通过 nginx-proxy + Let's Encrypt 使用 HTTPS)
   - 无需更改 Authelia 配置
   - 仅更改 docker-compose 标签和环境变量

---

## 实施状态

所有修复均已实施：

| 问题 | 状态 | 文件 |
|-------|--------|------|
| JWT 密钥废弃 | ✅ 已修复 | [authelia/configuration.yml](authelia/configuration.yml) |
| SMTP 冲突 | ✅ 已修复 | [authelia/configuration.yml](authelia/configuration.yml) + [docker-compose.yml](docker-compose.yml) |
| 会话 Cookie | ✅ 已修复 | [authelia/configuration.yml](authelia/configuration.yml) |
| Cookie 域名 | ✅ 已修复 | [authelia/configuration.yml](authelia/configuration.yml) |
| HTTP vs HTTPS | ✅ 已配置 | [authelia/configuration.yml](authelia/configuration.yml) |
| 文档 | ✅ 已完成 | [docs/authelia-setup.md](docs/authelia-setup.md) + [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md) |

---

## 快速入门

1. **更新配置文件** ✅ (已完成)
2. **创建包含 SMTP 的 `.env`**:
   ```bash
   SMTP_HOST=smtp.tinet.cat
   SMTP_PORT=587
   SMTP_USERNAME=your_email@example.com
   SMTP_PASSWORD=your_password
   SMTP_SENDER=Authelia <noreply@example.com>
   AUTHELIA_DOMAIN=auth.localhost
   ```

3. **生成密钥** (如果尚未完成):
   ```bash
   mkdir -p ./secrets
   openssl rand -base64 32 > ./secrets/authelia_jwt_secret.txt
   openssl rand -base64 32 > ./secrets/authelia_session_secret.txt
   chmod 600 ./secrets/*.txt
   ```

4. **启动服务**:
   ```bash
   docker compose up -d redis authelia
   docker compose logs -f authelia
   ```

5. **测试**:
   ```bash
   curl http://localhost:9091/api/health
   # 预期结果: 200 OK
   ```

6. **访问 UI**:
   ```
   浏览器访问: http://auth.localhost:9091
   ```

---

## 仍需帮助？

- **完整设置指南**: 请参阅 [docs/authelia-setup.md](docs/authelia-setup.md)
- **详细问题说明**: 请参阅 [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md)
- **故障排除**: 请参考 [docs/authelia-setup.md](docs/authelia-setup.md) 中的 "故障排除" 部分
- **官方文档**: https://www.authelia.com/configuration/
