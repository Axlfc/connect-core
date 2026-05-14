# AUDIT 02: ENVIRONMENT AND CONFIGURATION VARIABLE MANAGEMENT
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Secret Generation** | Initialization scripts (`init_env.sh`) use cryptographically secure methods (`openssl rand`) to generate secrets, which is an excellent practice. |
| ✓ | **File Protection** | The `.gitignore` file is correctly configured to exclude `secrets/` and `.env*`, preventing accidental exposure of credentials in the repository. |
| ⚠️ | **Mixed Methodology** | The project uses two methods for secret management simultaneously: **Docker Secrets** (secure) and **environment variables via `.env`** (less secure). This inconsistency is the main source of risk. |
| ✗ | **Potential Exposure** | Critical secrets such as `POSTGRES_PASSWORD` and `REDIS_PASSWORD` are injected into containers as environment variables, making them visible through `docker inspect`, logs, and potentially monitoring tools. |
| ✗ | **Input Validation** | Shell scripts, while robust, do not exhaustively validate user inputs in interactive mode, which could allow the injection of malicious characters into the `.env` file. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Secure Secret Generation:**
    *   The `init_env.sh` script uses `openssl rand` as the primary method for creating passwords and keys. This is the industrial best practice for generating secure random values.

2.  **`.env.example` File Handling:**
    *   The `generate_env_example.sh` script is remarkably intelligent. It identifies sensitive variables by patterns (`PASSWORD`, `KEY`, `TOKEN`, etc.) and empties them, while preserving non-sensitive configuration values. This ensures the example file is safe and useful.

3.  **Partial Usage of Docker Secrets:**
    *   The `docker-compose.yml` defines a `secrets:` block and correctly uses them in several services (e.g., `authelia`, `n8n-import`). This demonstrates knowledge of the correct way to handle secrets in Docker.
    *   **Example (`authelia` service):**
        ```yaml
        secrets:
          - authelia_jwt_secret
          - authelia_session_secret
        environment:
          - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
          - AUTHELIA_SESSION_SECRET_FILE=/run/secrets/authelia_session_secret
        ```
    *   This method is secure because the secret is mounted as a file in `/run/secrets/` inside the container and is never exposed as an environment variable.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **C-01** | **HIGH** | **Use of Environment Variables for Critical Secrets** | The main `postgres` and `redis` services receive their passwords through environment variables loaded from the `.env` file. An attacker with access to the Docker host could extract these credentials with the `docker inspect postgres` command. |
| **C-02** | **MEDIUM** | **Inconsistency in Secret Management** | The project uses Docker Secrets for some services (Authelia) but environment variables for others (Postgres, Redis). This lack of a single standard increases complexity, human error risk, and attack surface. |
| **C-03** | **LOW** | **Secret Visualization in Console** | `init_env.sh` displays a portion of the generated secret in the console. Although it is a truncated portion, this could expose the secret to shell history (`.bash_history`) or observers. |

---

### ⚠️ Warnings/Recommendations

1.  **`ENV_MANAGEMENT.md` Documentation:**
    *   The `ENV_MANAGEMENT.md` file exists but could be more explicit about the secret strategy. It should explain *why* Docker Secrets are preferred and warn about the risks of using environment variables for sensitive data.

2.  **Shell Script Hardening:**
    *   The `init_env.sh` and `generate_env_example.sh` scripts are complex. A good practice would be to add `set -o pipefail` at the beginning to ensure pipelines fail if an intermediate command fails.

---

### 🔧 Suggested Solutions

1.  **For C-01 and C-02 (Unify on Docker Secrets - CRITICAL):**
    *   **Step 1: Modify `docker-compose.yml`:**
        *   Reconfigure all services that currently use environment variables for secrets to use Docker Secrets instead.
        *   **Example for the `postgres` service:**
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
    *   **Step 2: Update `init_env.sh`:**
        *   Modify the script so that, instead of writing `POSTGRES_PASSWORD=secret_value` in the `.env`, it creates the corresponding file in the `secrets/` directory.
            ```bash
            # In init_env.sh, instead of sed:
            echo "$new_value" > secrets/postgres_password.txt
            chmod 600 secrets/postgres_password.txt
            # And remove the variable from .env
            sed -i '/^POSTGRES_PASSWORD=/d' "$TARGET_FILE"
            ```
        *   This centralizes all secrets in a single place (`/secrets`) managed with correct permissions.

2.  **For C-03 (Secret Visualization):**
    *   **Solution:** Modify `init_env.sh` to not show the generated value in the console. Simply inform the user that a value has been generated and saved.
        ```diff
        --- a/init_env.sh
        +++ b/init_env.sh
        @@ -145,7 +145,7 @@
             echo ""
             echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
             echo -e "${BLUE}Variable:${NC} $var"
-            echo -e "${BLUE}Generated value:${NC} ${new_value:0:20}...${new_value: -10}"
+            echo -e "${BLUE}Generated value:${NC} [HIDDEN FOR SECURITY]"
             echo -n "Use this value? (Y/n/customize): "
             read -r response
         ```
