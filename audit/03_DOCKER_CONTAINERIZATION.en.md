# AUDIT 03: DOCKER AND CONTAINERIZATION ANALYSIS
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Orchestration** | The `docker-compose.yml` file is **well-structured**, effectively using YAML anchors, profiles, and segmented networks. It demonstrates a solid architectural design. |
| ✓ | **Healthchecks** | Most critical services implement `healthchecks`, an excellent practice that ensures correct startup order and improves stack resilience. |
| ⚠️ | **Image Optimization** | Custom Dockerfiles are functional but **lack key optimizations**. They do not use multi-stage builds, resulting in larger than necessary images containing build tools not required at runtime. |
| ✗ | **Unpinned Dependencies** | Widespread use of the `:latest` tag in `docker-compose.yml` and Dockerfiles is a **critical risk to stability and security**. This leads to non-reproducible builds and the unexpected introduction of breaking changes. |
| ✗ | **Lack of Resource Limits** | The vast majority of services do not have CPU or memory limits defined in the `deploy.resources` section. This creates a risk of a single service consuming all host resources, causing a denial of service for the entire stack. |
| ✗ | **Inconsistencies and Bad Practices** | Several bad practices are observed, such as installing dependencies with `apt-get` without clearing the cache, and cloning `git` repositories from `master` branches instead of specific tags or commits. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **`docker-compose.yml` Structure:**
    *   Using YAML anchors (e.g., `x-ollama: &service-ollama`) to define base services is excellent for maintainability and reduces code duplication.
    *   Network segmentation into `frontend`, `backend`, `ai`, and `monitoring` (with the last three marked as `internal: true`) is a textbook network security implementation, effectively isolating services.
    *   Using profiles (`cpu`, `gpu-nvidia`, `monitoring`, etc.) allows granular control over which services start, adapting the stack to different hardware environments.

2.  **Healthcheck Definitions:**
    *   Services like `postgres`, `redis`, `n8n`, and `authelia` have well-defined `healthchecks`. This is crucial for the `depends_on.condition: service_healthy` directive, which prevents dependent services from starting before their dependencies are ready.

3.  **Volume Management:**
    *   The volume strategy is clear, using Docker named volumes for data persistence (e.g., `postgres_storage`) and `bind` mounts for configuration (e.g., `./authelia:/config`), which is a standard and robust practice.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **D-01** | **CRITICAL** | **Use of the `:latest` tag** | Multiple services (`qdrant`, `ollama`, `authelia`, `libretranslate`, `languagetool`, etc.) and Dockerfiles (`Dockerfile.comfyui`) use `:latest`. This breaks build reproducibility. An update in the remote image can break the application without warning or introduce a vulnerability. |
| **D-02** | **HIGH** | **Absence of Resource Limits** | Most services do not have a `deploy.resources` section with `limits`. A memory-leaking process or CPU spike in one service (e.g., `ollama` processing a complex request) could bring down the entire host server. |
| **D-03** | **HIGH** | **Non-Reproducible Builds in Dockerfiles** | `Dockerfile.comfyui` installs PyTorch dependencies from a `nightly` URL and clones git repositories from the `master` branch. This means building the same image at two different times can result in two completely different images with different versions and features. |
| **D-04** | **MEDIUM** | **Bloated Images** | Dockerfiles like `Dockerfile.runners` install build packages (`gcc`, `g++`, `build-base`) but do not remove them. This unnecessarily increases the final image size and, consequently, the attack surface. |
| **D-05** | **MEDIUM** | **Lack of APT Cache Cleaning** | In several Dockerfiles, `apt-get install` commands are executed without `&& rm -rf /var/lib/apt/lists/*` in the same `RUN` layer. This leaves unnecessary cache data in an image layer, increasing its size. |

### ⚠️ Warnings/Recommendations

1.  **Compose Configuration Versioning:**
    *   `docker-compose.yml` is version "3.8". While functional, consider updating to the latest `compose` specification to leverage new features in the future.

2.  **Exposed Port Clarity:**
    *   Some services expose ports only to `127.0.0.1` (e.g., `postgres`), which is a good security practice. However, others expose them to `0.0.0.0` (e.g., `whisper-stt`). Adding comments to justify why a port needs to be open to all interfaces is recommended to avoid confusion.

### 🔧 Suggested Solutions

1.  **For D-01 (Pin Versions - CRITICAL):**
    *   **Solution:** Perform an audit of each service using `:latest` and replace it with a specific and stable version tag.
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -201,7 +201,7 @@
         # QDRANT - Vector Database
         # ========================================
         qdrant:
        -  image: qdrant/qdrant:latest
        +  image: qdrant/qdrant:v1.9.0  # Or the latest stable version
           hostname: qdrant
           container_name: qdrant
           networks:
        ```

2.  **For D-02 (Add Resource Limits):**
    *   **Solution:** Add a `deploy.resources` section to each service, defining reasonable `limits` and `reservations`. These values should be adjusted based on load testing, but a starting point is essential.
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -216,6 +216,12 @@
           test: ["CMD-SHELL", "bash -c ':> /dev/tcp/localhost/6333' || exit 1"]
           interval: 5s
           timeout: 5s
           retries: 3
        +  deploy:
        +    resources:
        +      limits:
        +        cpus: '2.0'
        +        memory: 4G
        +      reservations:
        +        memory: 512M
         ```

3.  **For D-03 (Reproducible Builds):**
    *   **Solution for `Dockerfile.comfyui`:**
        *   Pin the base image version (`ghcr.io/ai-dock/comfyui:v1.2.3`).
        *   Download PyTorch dependencies, verify their checksums (SHA256), and then install them.
        *   When cloning `git` repositories, use `git clone --branch v1.0.0` or `git checkout <commit-hash>` instead of cloning from `master`.

4.  **For D-04 and D-05 (Optimize Images):**
    *   **Solution:** Use multi-stage builds and combine `RUN` commands to reduce the number of layers and clean up build artifacts.
        ```dockerfile
        # Example for Dockerfile.runners

        # Stage 1: Build
        FROM n8nio/runners:1.121.0 as builder
        USER root
        RUN apk add --no-cache gcc g++ musl-dev python3-dev build-base
        RUN python3 -m venv /home/runner/custom-venv
        # ... install all dependencies with pip ...

        # Stage 2: Final
        FROM n8nio/runners:1.121.0
        USER root
        # Copy only the venv from the build stage
        COPY --from=builder /home/runner/custom-venv /home/runner/custom-venv
        COPY n8n-task-runners.json /etc/n8n-task-runners.json
        # Ensure permissions and switch user
        RUN chown -R runner:runner /home/runner/custom-venv
        USER runner
        ENV PATH="/home/runner/custom-venv/bin:$PATH"
        ```
