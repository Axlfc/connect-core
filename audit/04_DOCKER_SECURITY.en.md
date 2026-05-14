# AUDIT 04: DOCKER SECURITY
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/04_DOCKER_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/04_DOCKER_SECURITY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/04_DOCKER_SECURITY.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/04_DOCKER_SECURITY.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Network Isolation** | Using custom Docker networks (`frontend`, `backend`, `ai`, `monitoring`) with most configured as `internal: true` is an **excellent security practice** that limits communication between services. |
| ✓ | **Least Privilege (Partial)** | Most services use `cap_drop: - ALL` and `security_opt: - no-new-privileges:true`, demonstrating a solid understanding of container security principles. |
| ✗ | **Running as Root** | Several critical containers, including `ollama` and those based on NVIDIA images (`whisper-stt`), run as the **`root` user**. A vulnerability in any of these applications would grant administrator privileges within the container. |
| ✗ | **Dangerous Linux Capabilities** | Multiple services (`postgres`, `forgejo`, `duplicati`) have the `DAC_OVERRIDE` capability added. This capability allows a process to bypass file read, write, and execute permission checks, undermining filesystem security. |
| ✗ | **Host Network Exposure** | The `fail2ban` service is configured with `network_mode: host`. This **completely breaks container network isolation**, giving it direct access to the host's network interfaces. This is extremely dangerous and nullifies many of containerization's security benefits. |
| ✗ | **Secrets in Logs** | `Dockerfile.matrix` contains an entrypoint script that **prints generated secrets (macaroon key, form secret, etc.) in the container logs** on the first start. This exposes critical credentials to anyone with access to Docker logs. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Least Privilege Principle Applied (partially):**
    *   Most services are configured with `security_opt: [no-new-privileges:true]`, preventing processes from gaining additional privileges.
    *   Using `cap_drop: [ALL]` as a default configuration and then adding only necessary capabilities (`cap_add`) is the correct strategy to follow.

2.  **Robust Network Isolation:**
    *   The network architecture is very well designed. Backend services are not accessible from the outside, and communication is segmented by function, limiting an attacker's lateral movement.

3.  **Use of Non-Root Users (partially):**
    *   Services like `redis` (`user: "999:999"`), `authelia`, and `n8n` (`user: "${PUID:-1000}:${PGID:-1000}"`) run correctly with non-privileged users, significantly reducing their risk.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **DS-01** | **CRITICAL** | **`fail2ban` with `network_mode: host`** | The container has full access to the host's network stack. It can sniff all traffic, connect to any `localhost` service on the host, and interfere with host firewall rules. A compromise of this container is equivalent to a network-level host compromise. |
| **DS-02** | **CRITICAL** | **Secrets Exposed in `matrix-synapse` Logs** | The entrypoint script in `Dockerfile.matrix` prints a "GENERATED SECRETS" block to standard output, which is captured by Docker logs. This makes session and federation secrets trivially accessible. |
| **DS-03** | **HIGH** | **Running as `root` in Key Containers** | `ollama`, `whisper-stt`, and `kokoro-tts` services run as `root`. A remote code execution vulnerability in any of these services would give an attacker full control within the container, with the ability to modify files, install malicious software, and attack other services on the network. |
| **DS-04** | **HIGH** | **Use of `DAC_OVERRIDE` Capability** | This capability, present in `postgres`, `matrix-postgres`, `forgejo`, and `duplicati`, allows a process to ignore file permissions. If an attacker compromises one of these containers, they could read/write files they would normally not have access to, potentially including sensitive configuration files or other users' data. |
| **DS-05** | **MEDIUM** | **Insecurely Mounted Docker Socket** | The `nginx-proxy` service mounts the Docker socket (`/var/run/docker.sock`) as `read-only`. This is good, but compromising `nginx-proxy` would still allow an attacker to obtain sensitive information about all other containers and the Docker host configuration. |

---

### ⚠️ Warnings/Recommendations

1.  **Read-Only Filesystems:**
    *   **Recommendation:** For containers that do not need to write data to their own filesystem (other than to mounted volumes), consider adding the `read_only: true` option. This can mitigate many classes of attacks that rely on writing binary files or malicious scripts.

2.  **Security Profiles (AppArmor/Seccomp):**
    *   **Recommendation:** Using `apparmor=docker-default` is a good starting point. For even greater security, custom AppArmor or Seccomp profiles could be created for each service, restricting the system calls each application can make.

---

### 🔧 Suggested Solutions

1.  **For DS-01 (`fail2ban` in `network_mode: host`):**
    *   **Solution:** This is a difficult configuration to change since `fail2ban` needs to modify host `iptables`. The safest solution is to **run `fail2ban` directly on the host**, outside of Docker. If it must remain in a container, investigate using a more specialized and "Rooted" container with tools like `nsenter` to execute commands in the host namespace in a controlled manner, instead of exposing the entire network stack.

2.  **For DS-02 (Secrets in Matrix Logs):**
    *   **Solution:** Modify `/scripts/entrypoint.sh` inside `Dockerfile.matrix` so that secrets are saved to a file inside the container with restricted permissions instead of being printed.
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

3.  **For DS-03 (Running as `root`):**
    *   **Solution for `ollama`:** The official `ollama` image now supports running as non-root. An `ollama` user should be created and volume permissions should be ensured correctly (`/root/.ollama` should change to `/home/ollama/.ollama`).
    *   **Solution for custom Dockerfiles (e.g., `whisper-stt`):** Add the following steps to the end of the Dockerfile:
        ```dockerfile
        # Create a non-root user
        RUN useradd -ms /bin/bash appuser

        # Ensure correct permissions on the app directory
        RUN chown -R appuser:appuser /app

        # Switch to the non-root user
        USER appuser

        # Adjust command/entrypoint if necessary
        CMD ["python", "/app/server.py"]
        ```

4.  **For DS-04 (`DAC_OVERRIDE`):**
    *   **Solution:** Investigate why each service needs this capability. Often, it is added to solve permission issues on mounted volumes. The correct solution is to **fix host permissions** (using the `setup-permissions.sh` script and ensuring `PUID`/`PGID` match) instead of granting dangerous capabilities. Remove `DAC_OVERRIDE` from the `cap_add` section of all services.
