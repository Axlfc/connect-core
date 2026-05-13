# Authelia Configuration Guide (v4.38.0+)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/authelia-setup.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/authelia-setup.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/authelia-setup.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/authelia-setup.ca.md)


## Overview

This guide addresses the configuration issues with Authelia 4.38.0+ in the cognito-stack Docker Compose environment. It covers the migration from deprecated configuration keys, proper SMTP setup, and local development with `.localhost` domains.

## Problems Solved

### 1. JWT Secret Deprecation (WARNING)
**Error**: `jwt_secret' is deprecated in 4.38.0 and has been replaced by 'identity_validation.reset_password.jwt_secret'`

**Solution**: Use the new key path:
```yaml
# OLD (deprecated):
jwt_secret: your_secret_here

# NEW (modern):
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
      # secret provided via environment variable
```

**Environment Variable**:
```bash
AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

---

### 2. SMTP Configuration Conflict (CRITICAL)
**Error**: `the new key already exists with value 'smtp://smtp.tinet.cat:556' but the deprecated keys and the new key can't both be configured`

**Root Cause**: Mixing old format (`host` and `port` keys) with new format (`address` key) simultaneously.

**Solution**: Use ONLY the modern `address` format:

```yaml
# OLD (deprecated and causes conflict):
notifier:
  smtp:
    host: smtp.example.com
    port: 587
    username: user@example.com
    password: password

# NEW (modern, no conflicts):
notifier:
  smtp:
    # Format: smtp[s]://[username@]host[:port]
    address: 'smtp://smtp.tinet.cat:587'
    sender: 'Authelia <noreply@example.com>'
    timeout: 5s
    tls:
      server_name: smtp.tinet.cat
      skip_verify: false
```

**Environment Variable Format**:
```bash
# Construct address from environment variables:
AUTHELIA_NOTIFIER_SMTP_ADDRESS=smtp://${SMTP_HOST}:${SMTP_PORT}
AUTHELIA_NOTIFIER_SMTP_USERNAME=${SMTP_USERNAME}
AUTHELIA_NOTIFIER_SMTP_PASSWORD=${SMTP_PASSWORD}
AUTHELIA_NOTIFIER_SMTP_SENDER=${SMTP_SENDER}
```

**Docker Compose Example** (from docker-compose.yml):
```yaml
environment:
  - AUTHELIA_NOTIFIER_SMTP_ADDRESS=smtp://${SMTP_HOST:-smtp.tinet.cat}:${SMTP_PORT:-587}
  - AUTHELIA_NOTIFIER_SMTP_USERNAME=${SMTP_USERNAME}
  - AUTHELIA_NOTIFIER_SMTP_PASSWORD=${SMTP_PASSWORD}
  - AUTHELIA_NOTIFIER_SMTP_SENDER=${SMTP_SENDER:-Authelia <noreply@example.com>}
```

**Required `.env` Variables**:
```bash
SMTP_HOST=smtp.tinet.cat
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_password
SMTP_SENDER=Authelia <noreply@example.com>
```

---

### 3. Session Cookie Configuration Error
**Error**: `session: option 'cookies' must be configured with the per cookie option 'default_redirection_url' but the global one is configured`

**Root Cause**: Authelia v4.38+ requires `default_redirection_url` to be configured per-cookie, not at the session level.

**Solution**: Move `default_redirection_url` inside the cookies array:

```yaml
# OLD (causes error):
session:
  name: authelia_session
  expiration: 1h
  default_redirection_url: https://forgejo.localhost  # ❌ WRONG
  cookies:
    - name: authelia_session
      domain: localhost

# NEW (correct):
session:
  name: authelia_session
  expiration: 1h
  cookies:
    - name: authelia_session
      domain: localhost
      default_redirection_url: https://forgejo.localhost  # ✅ CORRECT
      authelia_url: https://auth.localhost
      same_site: Lax
      secure: false  # Change to true in production with HTTPS

# OPTIONAL: Also set globally as fallback
default_redirection_url: 'https://forgejo.localhost'  # Session-level fallback
```

---

### 4. Invalid Cookie Domain for Localhost
**Error**: `domain config #1 (domain 'localhost'): option 'domain' is not a valid cookie domain: must have at least a single period or be an ip address`

**Root Cause**: Browsers reject `localhost` as a cookie domain in most contexts; requires a dot or be an IP address.

**Solution for Local Development**: Use `.localhost` suffix:

```yaml
# Option 1: Use localhost (works in Docker network)
session:
  cookies:
    - name: authelia_session
      domain: localhost      # ✅ Single label works in Docker network
      # For browser cookies, nginx-proxy rewrites domain

# Option 2: Use IP address
session:
  cookies:
    - name: authelia_session
      domain: 127.0.0.1
```

**Important**: Browser cookies and Docker internal DNS behave differently:
- **Docker internal**: Services resolve `localhost` directly (no cookie domain issue)
- **Browser**: Needs at least one dot in domain; use browser-compatible domain

**Recommended Setup**:
```yaml
session:
  cookies:
    - name: authelia_session
      domain: localhost              # Works in Docker network
      authelia_url: https://auth.localhost
      default_redirection_url: https://forgejo.localhost
      same_site: Lax
      secure: false                  # Change to true in production

default_redirection_url: 'https://forgejo.localhost'  # Global fallback
```

---

### 5. SMTP Address Conflict
**Error**: `notifier: smtp: option 'host' and 'port' can't be configured at the same time as 'address'`

**Solution**: This is the same as issue #2 above. Never mix `host`/`port` with `address`. Use ONLY `address`.

---

## Integration with nginx-proxy

Authelia is integrated with the `jwilder/nginx-proxy` service using a custom Nginx configuration file. This file, located at `nginx-proxy/authelia-location.conf`, contains the necessary directives to protect services with Authelia.

Services are automatically protected through nginx-proxy configuration without needing individual service modifications.

---

## User Management

User accounts are managed in the `authelia/users_database.yml` file.

### Adding a New User

To add a new user, you need to add a new entry to the `users` section of the `users_database.yml` file. Each user requires a `displayname`, a hashed `password`, an `email`, and a list of `groups`.

Example:

```yaml
users:
  admin:
    displayname: "Admin User"
    password: "$argon2id$v=19$m=65536,t=1,p=8$..."  # Hashed password
    email: admin@example.com
    groups:
      - admins
      - developers
  new_user:
    displayname: "New User"
    password: "$argon2id$v=19$m=65536,t=1,p=8$..."  # Hashed password
    email: new_user@example.com
    groups:
      - developers
```

### Generating a Password Hash

For security reasons, passwords are not stored in plaintext. You must generate an Argon2id hash for the user's password. You can generate a hash by running the following command:

```bash
docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password 'your-password'
```

Replace `'your-password'` with the desired password. The output will be a long string that you can copy and paste into the `password` field for the new user.

---

## Complete Working Configuration

### configuration.yml
```yaml
---
# Authelia Configuration (v4.38.0+)
# Modern configuration for local development and production

server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false  # nginx-proxy handles HTTPS

log:
  level: info

# JWT for identity validation
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
      # jwt_secret provided via AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE

# Session management
session:
  name: authelia_session
  expiration: 1h
  inactivity: 5m
  remember_me_duration: 1y
  cookies:
    - name: authelia_session
      domain: localhost
      authelia_url: https://auth.localhost
      default_redirection_url: https://forgejo.localhost
      same_site: Lax
      secure: false  # Change to true in production

  # Redis for distributed session storage
  redis:
    host: redis
    port: 6379
    # password via AUTHELIA_SESSION_REDIS_PASSWORD_FILE

# Storage (SQLite for local, PostgreSQL for production)
storage:
  local:
    path: /config/db.sqlite3

# File-based authentication
authentication_backend:
  file:
    path: /config/users_database.yml
    password:
      algorithm: argon2id
      iterations: 1
      salt_length: 16
      parallelism: 8
      memory: 64

# Access control policies
access_control:
  default_policy: deny

  rules:
    # Bypass Authelia endpoint itself
    - domain:
        - "auth.localhost"
      policy: bypass

    # One-factor authentication (password only)
    - domain:
        - "forgejo.localhost"
        - "n8n.localhost"
        - "comfyui.localhost"
        - "matrix.localhost"
        - "duplicati.localhost"
        - "translate.localhost"
        - "languagetool.localhost"
      policy: one_factor

# SMTP notifications (modern format)
notifier:
  disable_startup_check: false
  smtp:
    address: 'smtp://smtp.tinet.cat:587'
    timeout: 5s
    # username/password via environment variables
    sender: 'Authelia <noreply@example.com>'
    tls:
      server_name: smtp.tinet.cat
      skip_verify: false

# Rate limiting
regulation:
  max_retries: 3
  find_time: 10m
  ban_time: 15m

# Default redirect
default_redirection_url: 'https://forgejo.localhost'
```

---

## HTTP vs HTTPS

### Local Development (HTTP)
- Authelia serves HTTP on port 9091
- nginx-proxy handles connections (no SSL)
- Configuration: `tls.enabled: false` in authelia
- Session cookies: `secure: false`

### Production (HTTPS)
- Authelia served behind nginx-proxy with Let's Encrypt
- Configuration: `tls.enabled: false` (let reverse proxy handle TLS)
- Session cookies: `secure: true`
- SMTP: Use port 587 (STARTTLS) or 465 (implicit TLS)

---

## Testing Authelia

### 1. Verify Service is Running
```bash
docker compose logs -f authelia
```

### 2. Check Health Endpoint
```bash
curl -v http://localhost:9091/api/health
# Expected: HTTP 200
```

### 3. Test via Browser
```
http://auth.localhost:9091
# Should show Authelia login screen
```

### 4. Test Protected Service
1. Try accessing http://n8n.localhost
2. Should redirect to http://auth.localhost:9091/authentication
3. Login with credentials from `users_database.yml`
4. Should redirect back to http://n8n.localhost

---

## Troubleshooting

### Container Fails to Start
```bash
# Check logs for specific error
docker compose logs authelia

# Look for:
# - "level=error msg="Configuration:" (configuration issues)
# - "level=fatal" (fatal startup errors)
```

### SMTP Not Sending
1. Verify SMTP credentials in `.env`
2. Check SMTP server accepts connections on port 587
3. Enable debugging: `log.level: debug` in configuration.yml
4. Test SMTP manually: `telnet smtp.tinet.cat 587`

### Sessions Not Persisting
1. Verify Redis is running: `docker compose ps redis`
2. Check Redis password is correct in `.env`
3. Verify Redis connection in logs: `docker compose logs authelia | grep -i redis`

### Cookie Domain Issues
1. For browser access: ensure at least one dot in domain
2. For Docker internal: `localhost` works fine
3. Test with: `curl -v -b "authelia_session=test" http://auth.localhost:9091`

---

## Migration from Older Versions

### From 4.37.x to 4.38.0+

#### 1. JWT Secret Migration
```yaml
# OLD: jwt_secret at root level
jwt_secret: your_secret

# NEW: identity_validation.reset_password.jwt_secret
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
```

#### 2. SMTP Migration
```yaml
# OLD:
notifier:
  smtp:
    host: smtp.example.com
    port: 587
    username: user@example.com
    password: password

# NEW:
notifier:
  smtp:
    address: 'smtp://smtp.example.com:587'
```

---

## Additional Resources

- **Authelia Official Docs**: https://www.authelia.com/configuration/
- **Session Configuration**: https://www.authelia.com/configuration/session/
- **Notifier SMTP**: https://www.authelia.com/configuration/notifier/smtp/
- **Access Control**: https://www.authelia.com/configuration/access-control/

---

## Quick Reference: Common Issues

| Issue | Solution |
|-------|----------|
| JWT secret deprecated | Use `identity_validation.reset_password.jwt_secret` |
| SMTP address conflict | Use ONLY `address` format, never `host`+`port` |
| Cookie domain invalid | Use `localhost` for Docker, ensure dot for browser |
| Session not persisting | Check Redis is healthy and password is correct |
| Health check failing | Verify port 9091 is accessible, check logs |
| Redirect loops | Verify `default_redirection_url` in cookies config |
