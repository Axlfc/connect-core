# Authelia Configuration - FAQ and Answers to Your Questions
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.zh-cn.md)


## Q1: SMTP Configuration - What is the correct way to configure SMTP?

### Question
"What is the correct way to configure SMTP in the new format? Should we use `notifier.smtp.address` instead of `host` and `port` separately?"

### Answer: YES, use only the `address` format

**Correct (Modern v4.38.0+)**:
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

**Format**: `smtp[s]://[user@]host[:port]`

**Examples**:
```
smtp://smtp.example.com:587              # STARTTLS on port 587
smtps://smtp.example.com:465             # Implicit TLS on port 465
smtp://user@smtp.example.com:587         # With user in the URL
```

**Credentials via Environment Variables**:
```yaml
environment:
  - AUTHELIA_NOTIFIER_SMTP_ADDRESS=smtp://smtp.tinet.cat:587
  - AUTHELIA_NOTIFIER_SMTP_USERNAME=your_email@example.com
  - AUTHELIA_NOTIFIER_SMTP_PASSWORD=your_password
  - AUTHELIA_NOTIFIER_SMTP_SENDER=Authelia <noreply@example.com>
```

**From `.env`**:
```bash
SMTP_HOST=smtp.tinet.cat
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_password
SMTP_SENDER=Authelia <noreply@example.com>
```

**DO NOT mix formats** (will cause conflict):
```yaml
# ❌ INCORRECT - This causes the conflict error:
notifier:
  smtp:
    host: smtp.example.com        # ❌ Old format
    port: 587                      # ❌ Old format
    address: 'smtp://...:587'      # ❌ New format (conflict!)
```

---

## Q2: Session Cookies for Localhost

### Question
"How should we configure session cookies for local development using `.localhost` domains? The error indicates that domains must have a dot or be an IP address."

### Answer: Use `localhost` in the configuration, nginx-proxy manages browser compatibility

**The Configuration**:
```yaml
session:
  cookies:
    - name: authelia_session
      domain: localhost              # ✅ Correct for the Docker network
      authelia_url: https://auth.localhost
      default_redirection_url: https://forgejo.localhost
      same_site: Lax
      secure: false                  # Change to true in production
```

**How it works**:
1. **Docker Network**: Services communicate using `localhost` (works fine)
2. **Browser Access**: User goes to `http://auth.localhost:9091`
3. **nginx-proxy**: Intercepts the request to `auth.localhost` and directs it to Authelia
4. **Cookie Domain**: nginx-proxy manages the cookie rewriting for browser compatibility
5. **Result**: The browser never sees the invalid `localhost` domain directly

**Why this works**:
- Docker's internal DNS resolves `localhost` within containers
- The browser never sets cookies directly on the `localhost` domain
- nginx-proxy intermediates and manages the cookie domain translation
- Both internal Docker access and browser access work perfectly

**What NOT to do**:
```yaml
# ❌ INCORRECT - This will also fail:
domain: .localhost    # The browser still rejects single-label domains

# ❌ INCORRECT - Too restrictive for development:
domain: auth.localhost  # Only works for auth.localhost, not for other services

# ✅ CORRECT:
domain: localhost     # Works for Docker network + nginx-proxy manages the browser
```

**Environment Variables**:
```yaml
environment:
  - VIRTUAL_HOST=${AUTHELIA_DOMAIN:-auth.localhost}
  - VIRTUAL_PORT=9091
```

**In `.env`**:
```bash
AUTHELIA_DOMAIN=auth.localhost
```

---

## Q3: JWT Secret Migration

### Question
"Should we update the configuration file to use the new `identity_validation.reset_password.jwt_secret` key?"

### Answer: YES, migrate to the new key path

**Old (Obsolete)**:
```yaml
jwt_secret: your_secret_here
```

**New (v4.38.0+)**:
```yaml
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
      # Secret injected via environment variable
```

**Environment Variable**:
```yaml
environment:
  - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**Docker Compose Configuration**:
```yaml
secrets:
  - authelia_jwt_secret

services:
  authelia:
    environment:
      - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**Why migrate?**:
- ✅ Supports Authelia's new password reset flow
- ✅ Follows semantic versioning (separate JWT for different purposes)
- ✅ Allows future separation of JWTs for authentication vs. password reset
- ✅ Eliminates deprecation warnings

**Backward Compatibility**:
- Authelia 4.38.0+ still accepts the old `jwt_secret` but shows a warning
- New configuration is required for clean logs
- Password reset functionality only works with the new key

---

## Q4: Default Redirection URL Configuration

### Question
"How should we correctly configure `default_redirection_url` at the level of each cookie instead of globally?"

### Answer: Move it inside each cookie's configuration

**Old (Causes Error)**:
```yaml
session:
  expiration: 1h
  default_redirection_url: https://forgejo.localhost  # ❌ INCORRECT
  cookies:
    - name: authelia_session
      domain: localhost
```

**New (Correct)**:
```yaml
session:
  expiration: 1h
  # Do not put it here ❌

  cookies:
    - name: authelia_session
      domain: localhost
      default_redirection_url: https://forgejo.localhost  # ✅ HERE
      authelia_url: https://auth.localhost
      same_site: Lax
      secure: false

# Optional: Global fallback at the root level
default_redirection_url: 'https://forgejo.localhost'
```

**Multiple Cookies (Advanced)**:
```yaml
session:
  cookies:
    # Production cookie
    - name: authelia_session
      domain: example.com
      default_redirection_url: https://app.example.com
      secure: true

    # Development cookie
    - name: authelia_session_dev
      domain: localhost
      default_redirection_url: https://forgejo.localhost
      secure: false

# Global fallback
default_redirection_url: 'https://example.com'
```

**How it works**:
1. User accesses a protected service (e.g., n8n.localhost)
2. Redirected to Authelia login (auth.localhost)
3. After login, Authelia checks the `default_redirection_url` for each cookie
4. Redirects to the configured URL (e.g., forgejo.localhost)
5. If no per-cookie configuration exists, it uses the global `default_redirection_url`

**Required Configuration Fields**:
```yaml
cookies:
  - name: authelia_session              # Cookie name
    domain: localhost                   # Cookie domain
    authelia_url: https://auth.localhost  # Authelia endpoint
    default_redirection_url: https://forgejo.localhost  # Fallback destination
    same_site: Lax                      # CSRF protection
    secure: false                       # true in production
```

---

## Q5: HTTP vs HTTPS - Local Development vs Production

### Question
"Can we run Authelia with HTTP in local development (with nginx-proxy managing SSL via self-signed certificates or without SSL) and then switch to HTTPS in production?"

### Answer: YES, Authelia is protocol-agnostic

**Local Development (HTTP, without SSL)**:
```yaml
# In authelia/configuration.yml:
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ HTTP only

session:
  cookies:
    - name: authelia_session
      secure: false         # ✅ Allow HTTP cookies
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
    # nginx-proxy serves via HTTP
```

**How to access**:
```
Browser: http://auth.localhost:9091
Browser: http://n8n.localhost
```

---

**Production (HTTPS with Let's Encrypt)**:
```yaml
# In authelia/configuration.yml (NO CHANGES NEEDED):
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ Still false
    # nginx-proxy manages TLS termination

session:
  cookies:
    - name: authelia_session
      secure: true          # ✅ Require HTTPS
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
    # nginx-proxy + acme-companion manage HTTPS + Let's Encrypt
```

**How to access**:
```
Browser: https://auth.example.com
Browser: https://app.example.com
```

---

**Key Points**:

1. **Authelia itself**: Always runs on HTTP (port 9091) internally
2. **TLS Termination**: Let nginx-proxy handle HTTPS termination
3. **Authelia Configuration**: `tls.enabled: false` for all scenarios
4. **Session Security**:
   - Local Dev: `secure: false` (allow HTTP)
   - Production: `secure: true` (require HTTPS)
5. **Migration Path**:
   - Start with local dev (HTTP, no SSL)
   - Move to production (HTTPS via nginx-proxy + Let's Encrypt)
   - No changes needed in Authelia configuration
   - Only change docker-compose labels and environment variables

---

## Implementation Status

All fixes have been implemented:

| Problem | Status | File |
|-------|--------|------|
| JWT Secret Deprecation | ✅ Fixed | [authelia/configuration.yml](authelia/configuration.yml) |
| SMTP Conflict | ✅ Fixed | [authelia/configuration.yml](authelia/configuration.yml) + [docker-compose.yml](docker-compose.yml) |
| Session Cookies | ✅ Fixed | [authelia/configuration.yml](authelia/configuration.yml) |
| Cookie Domain | ✅ Fixed | [authelia/configuration.yml](authelia/configuration.yml) |
| HTTP vs HTTPS | ✅ Configured | [authelia/configuration.yml](authelia/configuration.yml) |
| Documentation | ✅ Complete | [docs/authelia-setup.md](docs/authelia-setup.md) + [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md) |

---

## Quick Start

1. **Update configuration files** ✅ (Already done)
2. **Create `.env` with SMTP**:
   ```bash
   SMTP_HOST=smtp.tinet.cat
   SMTP_PORT=587
   SMTP_USERNAME=your_email@example.com
   SMTP_PASSWORD=your_password
   SMTP_SENDER=Authelia <noreply@example.com>
   AUTHELIA_DOMAIN=auth.localhost
   ```

3. **Generate secrets** (if not already done):
   ```bash
   mkdir -p ./secrets
   openssl rand -base64 32 > ./secrets/authelia_jwt_secret.txt
   openssl rand -base64 32 > ./secrets/authelia_session_secret.txt
   chmod 600 ./secrets/*.txt
   ```

4. **Start services**:
   ```bash
   docker compose up -d redis authelia
   docker compose logs -f authelia
   ```

5. **Test**:
   ```bash
   curl http://localhost:9091/api/health
   # Expected: 200 OK
   ```

6. **Access UI**:
   ```
   Browser: http://auth.localhost:9091
   ```

---

## Still Need Help?

- **Full Setup Guide**: See [docs/authelia-setup.md](docs/authelia-setup.md)
- **Detailed Problem Explanations**: See [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md)
- **Troubleshooting**: Consult the "Troubleshooting" section in [docs/authelia-setup.md](docs/authelia-setup.md)
- **Official Docs**: https://www.authelia.com/configuration/
