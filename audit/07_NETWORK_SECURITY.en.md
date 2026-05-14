# AUDIT 07: NETWORK SECURITY AND FIREWALL
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Internal Network Segmentation** | The Docker Compose network architecture is **excellently designed**, using `internal` networks to isolate backend services and limit the internal attack surface. |
| ⚠️ | **`fail2ban` Configuration** | The `fail2ban` service is implemented, demonstrating an intent to protect against brute-force attacks. However, its configuration is **too simplistic**, only monitoring failed login attempts through Nginx logs. |
| ✗ | **`fail2ban` in `network_mode: host`** | This is a **critical security design flaw**. Running `fail2ban` in host network mode breaks container isolation, granting it unrestricted access to the host system's network interfaces. A compromise of this container could compromise the entire host network. |
| ✗ | **Lack of Egress Control** | There are no network policies restricting outbound traffic from containers. If a container is compromised, it could be used to download malware, connect to command-and-control (C2) servers, or attack other systems on the internet without any restriction. |
| ✗ | **Unnecessary Port Exposure** | Multiple services expose their ports directly to the host interfaces (e.g., `postgres` on `127.0.0.1:5432`, `whisper-stt` on `0.0.0.0:9001`). In a microservices architecture, communication should occur primarily through the internal Docker network, and only the reverse proxy should expose ports externally. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Service Isolation by Network:**
    *   Creating separate networks (`frontend`, `backend`, `ai`, `monitoring`) and using `internal: true` for networks that do not need external access is the correct implementation of the principle of least privilege at the network level. This prevents a compromised service in the backend (e.g., a database) from being accessed directly from the outside.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **N-01** | **CRITICAL** | **`fail2ban` with `network_mode: host`** | The `fail2ban` container nullifies Docker network isolation. It can monitor, interfere with, and manipulate host network traffic. An attacker who compromises this container could evade the main firewall, attack host services that are not publicly exposed, and obtain a persistent foothold in the host network. |
| **N-02** | **HIGH** | **Insufficient `fail2ban` Filters** | The current configuration only blocks IPs that generate 401 errors on specific login endpoints. It does not protect against a wide range of common attacks, such as directory scanning, SQL injection, XSS, or application-level (layer 7) denial-of-service attacks. It provides a false sense of security. |
| **N-03** | **MEDIUM** | **Direct Backend Port Exposure** | Services like `postgres` and `redis` expose their ports to `127.0.0.1` on the host. While this is not publicly accessible, it allows any other process running on the same host (including other misconfigured containers) to attempt to connect directly to the database or cache, bypassing application layers. |
| **N-04** | **MEDIUM** | **Lack of Egress Traffic Control** | Containers can initiate outbound connections to any destination on the internet. If an attacker manages to execute code in a container (e.g., `ollama`), they could use it to download hacking tools, exfiltrate data to an external server, or participate in a botnet. |

### ⚠️ Warnings/Recommendations

1.  **Internal Traffic Visibility:**
    *   Traffic between containers on the same Docker network is not encrypted (TLS). For very high-security environments (e.g., PCI DSS compliance), implementing a service mesh like Istio or Linkerd could be considered to force encryption of all internal traffic (mTLS).

### 🔧 Suggested Solutions

1.  **For N-01 and N-02 (Redesign `fail2ban` Strategy):**
    *   **Ideal Solution (Recommended):** Remove the `fail2ban` container. Install and configure `fail2ban` **directly on the host operating system**. This gives it legitimate and secure access to host logs and `iptables` without breaking the Docker security model.
    *   **Alternative Solution (If it must be in a container):**
        1.  Remove `network_mode: host`.
        2.  Add `NET_ADMIN` and `NET_RAW` capabilities to allow `iptables` manipulation.
        3.  Mount the host's `iptables` log file inside the container so it can see its own actions.
        4.  Massively expand filters in `filter.d` to include `nginx-badbots`, `nginx-noscript`, `nginx-http-auth`, and other predefined `fail2ban` rules for more complete protection.

2.  **For N-03 (Limit Port Exposure):**
    *   **Solution:** Review each service in `docker-compose.yml` and remove any `ports` mapping that is not strictly necessary for external access (managed by `nginx-proxy`) or for local debugging. Communication between services should take place through the Docker network using service names as DNS (e.g., `postgres:5432`).
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -140,8 +140,6 @@
         hostname: postgres
         container_name: postgres
         networks:
           - backend
         restart: unless-stopped
-        ports:
-          - "127.0.0.1:5432:5432"
         secrets:
           - postgres_password
           - postgres_user
        ```

3.  **For N-04 (Egress Control):**
    *   **Solution:** Create a dedicated Docker network for internet access and attach only to containers that explicitly need it.
        1.  **Define an egress network in `docker-compose.yml`:**
            ```yaml
            networks:
              egress_allowed:
                driver: bridge
            ```
        2.  **Modify the host firewall (iptables):** Add rules to allow `FORWARD` traffic only from the `egress_allowed` network subnet to the outside, and deny `FORWARD` from other Docker networks.
            ```bash
            # Example iptables rule (requires correct subnet)
            DOCKER_EGRESS_NW="172.x.y.0/24" # Egress allowed network subnet
            iptables -A FORWARD -i br-$(docker network ls | grep egress_allowed | awk '{print $1}') -o <external_iface> -j ACCEPT
            iptables -A FORWARD -i docker0 -o <external_iface> -j DROP
            ```
        3.  **Attach containers to the network:** Only containers needing internet access (e.g., `n8n` for webhooks) would be added to the `egress_allowed` network.
