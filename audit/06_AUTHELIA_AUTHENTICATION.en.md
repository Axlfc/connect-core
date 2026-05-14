# AUDIT 06: AUTHELIA - AUTHENTICATION AND AUTHORIZATION
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Integration and SSO** | The configuration of Authelia as a `forward auth` provider for Nginx is **correctly implemented**. The Single Sign-On (SSO) flow is conceptually solid. |
| ✓ | **Access Policy** | The `default_policy: deny` policy is **best security practice**, forcing each service to be explicitly authorized. Domain-based rules are clear and easy to manage. |
| ✗ | **Password Policy (Hashing)** | The `argon2id` hash algorithm configuration is **critically weak**, using only `iterations: 1`. This makes stored password hashes vulnerable to high-speed offline cracking attacks. |
| ✗ | **Session Security** | The session cookie is configured with `secure: false`, a **development-only** parameter. In production, this would allow the session cookie to be transmitted unencrypted over HTTP, exposing it to session hijacking attacks. |
| ⚠️ | **Storage Backend** | The system uses a local SQLite database for storage. While functional, it is not recommended for production environments with high concurrency or requiring high availability. |
| ⚠️ | **Secret Management** | The `admin` user password is loaded from an environment variable (`AUTHELIA_ADMIN_PASSWORD`), perpetuating the inconsistent and less secure secret management strategy identified in **AUDIT 02**. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Zero Trust Model:**
    *   The `access_control.default_policy: deny` policy is excellent. It ensures that no new service is accidentally exposed without an explicit authorization rule.

2.  **Anti-Brute Force Protection:**
    *   The `regulation` section is configured with reasonable values (`max_retries: 3`, `ban_time: 15m`). This provides an effective first line of defense against online password guessing attacks.

3.  **Session Secret Management:**
    *   Authelia session and JWT secrets are correctly managed via Docker Secrets (`AUTHELIA_SESSION_SECRET_FILE`, `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE`), the most secure way to handle these types of credentials.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **A-01** | **CRITICAL** | **Weak Password Hashing** | The `password.iterations: 1` setting for `argon2id` is dangerously low. Argon2id is designed to be computationally intensive. With 1 iteration, an attacker who obtains the `users_database.yml` file could crack passwords thousands of times faster than expected, making recovery of weak passwords trivial. |
| **A-02** | **CRITICAL** | **Insecure Session Cookie** | The `cookies.secure: false` setting tells the browser it can send the session cookie over unencrypted HTTP connections. If for any reason (e.g., an `sslstrip` attack) a user connects via HTTP, their session cookie would be intercepted, allowing an attacker to take full control of their account. |
| **A-03** | **MEDIUM** | **Excessive "Remember Me" Duration** | The `remember_me_duration` is set to `1y` (one year). If a user's session is compromised, the attacker would have potential access for a full year, even if the user does not actively log in. |

### ⚠️ Warnings/Recommendations

1.  **Production Backend:**
    *   **Recommendation:** For a production environment, migrate Authelia `storage` from SQLite to a more robust database like PostgreSQL. This improves performance, concurrency, and reliability. Authelia can use the same Postgres instance already in the stack (with a separate database).

2.  **Authelia Documentation:**
    *   The project contains multiple `AUTHELIA_*.md` files. It would be beneficial to consolidate them into a single guide within the `/docs` or `/audit` directory to clarify the authentication architecture and design decisions.

### 🔧 Suggested Solutions

1.  **For A-01 (Strengthen Hashing - CRITICAL):**
    *   **Solution:** Increase the number of iterations in `authelia/configuration.yml` to a secure value. Authelia's recommended value is `2`, but `3` or `4` offer an even better balance between security and performance.
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
    *   **Important:** After applying this change, all existing user passwords must be reset so they are re-hashed with the new configuration.

2.  **For A-02 (Secure Session Cookie - CRITICAL):**
    *   **Solution:** Change the `secure` value to `true` in the cookie configuration. This must be done before any deployment to an environment using HTTPS.
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -40,7 +40,7 @@
       authelia_url: https://auth.localhost
       default_redirection_url: https://forgejo.localhost
       same_site: Lax
-      secure: false  # Set to true in production with HTTPS
+      secure: true
        ```

3.  **For A-03 (Reduce Session Duration):**
    *   **Solution:** Reduce the `remember_me_duration` to a more conservative period, such as `1M` (one month) or `14d` (two weeks), to limit the exposure window in case of session compromise.
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -32,7 +32,7 @@
   # session.secret is provided via AUTHELIA_SESSION_SECRET_FILE
   expiration: 1h
   inactivity: 5m
-  remember_me_duration: 1y
+  remember_me_duration: 30d
   # Per-cookie configuration for local development with .localhost domains
   cookies:
     - name: authelia_session
        ```
