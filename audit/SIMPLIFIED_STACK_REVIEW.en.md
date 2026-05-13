# Architectural Review: Simplified-Stack vs. Root Project
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/SIMPLIFIED_STACK_REVIEW.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/SIMPLIFIED_STACK_REVIEW.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/SIMPLIFIED_STACK_REVIEW.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/SIMPLIFIED_STACK_REVIEW.zh-cn.md)


This document provides a critical analysis of the `simplified-stack` compared to the mature `root project` (source of truth). It identifies structural differences and identifies areas for cross-pollination while respecting their distinct design goals.

---

## 1. Executive Summary: Distinct Projects, Different Goals

The `root project` and `simplified-stack` are **independent projects** designed for different target audiences and environments:

*   **Root Project**: A mature, "security-first" architecture designed for production-ready deployments. It prioritizes isolation, hardening, and automated infrastructure (monitoring, auth).
*   **Simplified-Stack**: A "developer-first" lite version optimized for local iteration and ease of setup. It intentionally trades off advanced security hardening for a lower barrier to entry.

While the `simplified-stack` introduces exploratory components like **Drupal** and **Obsidian**, the `root project` remains the stable source of truth for n8n-centric AI orchestration.

---

## 2. Structural Differences

| Feature | Root Project (Source of Truth) | Simplified-Stack (Lite Version) |
| :--- | :--- | :--- |
| **Primary Orchestrator** | **n8n** (Logic-heavy) | **Drupal** (Content/UI-heavy) |
| **Database Architecture** | Distributed (3 Postgres instances) | **Unified** (1 pgvector instance) |
| **Persistence** | Named Volumes + Bind Mounts | **Pure Bind Mounts** (`./data`) |
| **Networking** | Strict Subnets & Internal Isolation | Flat bridge networks |
| **Security Layer** | Authelia (SSO) + Nginx Proxy | None (Direct port access) |
| **Hardware Profiles** | Highly granular (Nvidia, AMD, CPU, ARM64) | Grouped (Nvidia, AMD, CPU) |

---

## 3. Intentional Gaps in Simplified-Stack

To maintain its "lite" and "developer-friendly" status, the `simplified-stack` intentionally omits several features present in Root:

### ⚠️ Security Hardening
Unlike the Root project, Simplified does not implement advanced hardening like `cap_drop`, `security_opt`, or Docker Secrets. This is an **intentional trade-off** to simplify local development and avoid configuration friction.

### ❌ n8n Initialization Automation
Root includes a dedicated `n8n-import` service for pre-loading credentials. Porting this "batteries-included" feature to Simplified would improve its developer experience without adding significant complexity.

### ❌ Enterprise Monitoring & Voice
Simplified lacks the monitoring stack (Prometheus/Grafana) and high-load voice services (Whisper/Kokoro). While omitted for "lightness," their absence limits the stack's utility for advanced AI agents.

---

## 4. Cross-Pollination Candidates for Root Project

The `simplified-stack` serves as an experimental ground for several features that could enhance the `root` project:

### ✅ Bind Mount Transparency
Simplified's use of a structured `./data` bind-mount approach makes the filesystem more accessible for manual backups and debugging compared to named volumes.

### ✅ Obsidian as KM Interface
The inclusion of **Obsidian** provides a superior user interface for managing the Markdown-based knowledge base used in RAG workflows.

### ✅ pgvector Optimization
While Root should maintain its distributed database architecture for isolation, adopting the `pgvector` image variant (as used in Simplified) would enhance its native AI capabilities.

---

## 5. Potential Issues & Observations in Simplified

### ⚠️ Experimental Orchestration (Drupal)
In the `simplified-stack`, **Drupal** is used as the primary orchestrator. This is an **experimental UI/CMS layer** and is not intended to replace the stable n8n-centric logic used in the Root project.

### ⚠️ User Permissions
The `simplified-stack` runs Ollama as `root` to ensure "plug-and-play" compatibility with bind mounts. While this introduces a security trade-off, it aligns with the goal of prioritizing developer ease-of-use over hardening.

### ⚠️ Unpinned Image Versions
Simplified uses `n8n:latest` and `runners:latest`. For improved stability even in a lite stack, pinning these to a known stable version (like `1.121.0`) is recommended.

---

## 6. Target Audiences & Use Cases

| Project | Ideal User | Environment |
| :--- | :--- | :--- |
| **Root Project** | System Administrators, AI Engineers | Production, VPS, Home Lab (exposed to net) |
| **Simplified-Stack** | Individual Developers, Content Creators | Local Laptop, WSL2, Offline / Air-gapped |

---

## 7. Actionable Feedback & Code Examples

### 💡 Strategy A: Port `n8n-import` to Simplified
To give Simplified the "batteries-included" feel, add this service to `simplified-stack/docker-compose.yml`:

```yaml
  n8n-import:
    image: n8nio/n8n:1.121.0
    container_name: n8n-import
    profiles: ["minimal"]
    restart: "no"
    depends_on:
      postgres: { condition: service_healthy }
    volumes:
      - ./data/n8n:/home/node/.n8n
      - ./n8n/demo-data:/demo-data:ro
    entrypoint: /bin/sh
    command:
      - "-c"
      - "n8n import:credentials --separate --input=/demo-data/credentials && n8n import:workflow --separate --input=/demo-data/workflows"
```

### 💡 Strategy B: Transition to Docker Secrets
Even for a "lite" stack, Docker Secrets can be used without complexity by using the `file` provider pointing to the `.env` file or dedicated files.

```yaml
# In simplified-stack/docker-compose.yml
secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  postgres:
    secrets:
      - db_password
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/db_password
```

---

## 8. Conclusion

The `root project` and `simplified-stack` represent two distinct but complementary approaches to AI orchestration. By maintaining their **architectural independence**, they can serve different needs: Root as the secure, production-hardened core, and Simplified as the experimental, developer-friendly lite version. Cross-pollination—specifically adopting **Obsidian** and **bind-mount transparency**—remains the most beneficial path for the Root project's evolution.
