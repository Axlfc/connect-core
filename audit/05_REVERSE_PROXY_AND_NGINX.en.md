# AUDIT 05: REVERSE PROXY AND NGINX
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Authelia Integration** | The `forward auth` configuration for Authelia integration is **correct and secure**. The use of an `internal` block and correct header transmission (`X-Forwarded-*`) follows best practices. |
| ✓ | **Configuration Structure** | The configuration structure using `vhost.d` to apply per-service protection is **modular and scalable**, allowing granular control over which endpoints are protected. |
| ✗ | **Missing Security Headers** | The Nginx configuration **completely lacks explicit security headers**. HSTS, CSP, X-Frame-Options, Permissions-Policy, and other essential proxy "hardening" headers are not being configured. |
| ✗ | **Weak SSL/TLS Configuration** | No SSL/TLS policy is specified. This means reliance on `nginx-proxy` default values, which may allow weak ciphers or obsolete TLS versions, exposing communication to potential downgrade attacks. |
| ⚠️ | **No Rate Limiting** | There is no `rate limiting` configuration at the reverse proxy level. This leaves backend services vulnerable to Denial of Service (DoS) attacks or brute-force attempts that could exhaust resources. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Forward Auth Implementation:**
    *   The `nginx-proxy/authelia-location.conf` file is perfectly configured. It uses the `internal` directive to prevent external access to the verification endpoint and correctly passes all necessary headers for Authelia to make authorization decisions.
    *   Files in `vhost.d` (e.g., `n8n.localhost`) include this block and correctly configure the `auth_request` directive, ensuring unauthenticated requests are intercepted.

2.  **Configuration Modularity:**
    *   The `vhost.d` system allows for selective authentication application. This is flexible and allows certain endpoints (like webhooks) to remain unprotected if necessary without compromising the security of the rest of the application.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **RP-01** | **HIGH** | **Absence of Critical Security Headers** | Without HSTS (`Strict-Transport-Security`), browsers are not forced to use HTTPS, opening the door to `sslstrip` attacks. Without `X-Frame-Options` or `Content-Security-Policy: frame-ancestors`, the site is vulnerable to *Clickjacking* attacks. The lack of a robust CSP allows Cross-Site Scripting (XSS) attacks. |
| **RP-02** | **MEDIUM** | **Reliance on Default SSL/TLS Configurations** | Not explicitly defining allowed TLS protocols and ciphers can cause the server to negotiate connections with weak or insecure algorithms if requested by a client. |
| **RP-03** | **MEDIUM** | **Lack of Edge Rate Limiting** | Without `rate limiting`, an attacker can make an unlimited number of requests to backend services to guess credentials, look for vulnerabilities, or simply exhaust server resources (CPU, memory, database connections). |

### ⚠️ Warnings/Recommendations

1.  **Compression:**
    *   No explicit compression configuration (Gzip/Brotli) is observed. Activating it can significantly improve load times for end users.

2.  **Custom Logging:**
    *   The Nginx log format is standard. It could be customized to include more useful information for debugging and security analysis, such as `upstream` response times or Authelia `headers`.

### 🔧 Suggested Solutions

1.  **For RP-01 and RP-02 (Add Headers and SSL/TLS Hardening):**
    *   **Solution:** Create a new global configuration file, for example `nginx-proxy/conf.d/hardening.conf`, and add the following directives. This will apply a solid security policy to all services behind the proxy.
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf

        # --- SSL/TLS Hardening ---
        # Force TLS 1.2 and 1.3, and modern, secure ciphers.
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;

        # --- Security Headers ---
        # Force HTTPS for 1 year, including subdomains.
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        # Prevent Clickjacking.
        add_header X-Frame-Options "SAMEORIGIN" always;

        # Prevent browser MIME type sniffing.
        add_header X-Content-Type-Options "nosniff" always;

        # Activate browser XSS filters.
        add_header X-XSS-Protection "1; mode=block" always;

        # Control information sent in the Referer header.
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # (Optional but recommended) Content Security Policy (CSP) - Requires fine-tuning!
        # This is a restrictive policy; start with something more permissive if it causes issues.
        # add_header Content-Security-Policy "default-src 'self'; script-src 'self'; img-src 'self'; style-src 'self'; object-src 'none';" always;
        ```

2.  **For RP-03 (Implement Rate Limiting):**
    *   **Solution:** Add a `limit_req_zone` configuration to the same `hardening.conf` file to establish global limits.
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf (continued)

        # --- Rate Limiting ---
        # Define a memory zone to track IPs. 10m can store ~160,000 IPs.
        limit_req_zone $binary_remote_addr zone=global_limit:10m rate=10r/s;

        # Apply limit to all locations.
        limit_req zone=global_limit burst=20 nodelay;
        ```
        *   **Note:** This configuration limits each IP to 10 requests per second, with a "burst" of 20. These values are a starting point and should be adjusted based on expected application traffic.
