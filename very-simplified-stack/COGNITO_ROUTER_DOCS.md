# 🧠 Cognito-Codex Intelligent Development Router

This documentation describes the architecture, security rules, policies, and operating guides for the **Cognito-Codex Intelligent Router** implemented inside `CONNECT-CORE/very-simplified-stack`.

---

## 🏛️ Architecture Decision Records (ADRs)

### ADR-001: Control-Plane and Host-Worker Separation
* **Status:** Approved
* **Context:** Running the LLM orchestration / control plane inside a Docker container provides isolation and security, but direct filesystem manipulation, command execution, and official Codex app-server launch require host-side permissions as the local CachyOS user.
* **Decision:** Split the router into `cognito-backend` (Docker-based control plane & routing decision maker) and `cognito-worker` (host-side local desktop agent).
* **Consequences:** The control plane holds the policy engine and session storage. The worker acts as the local system orchestrator, maintaining a restricted workspace allowlist.

### ADR-002: Granular Trust and Legacy Migration
* **Status:** Approved
* **Context:** The legacy `ProjectTrustStore` mapped repositories to a single boolean value, granting unlimited shell and file mutation rights. This was insecure.
* **Decision:** Replace the boolean trust model with granular permissions: `read`, `write`, `shell`, `network`, `git_commit`, `git_push`, `extensions`, `secrets`, `destructive_operations`. Migrate legacy boolean records idempotently.
* **Consequences:** A legacy `trusted: true` maps to read/write enabled, shell and git_commit set to `approval`, and others set to `false`, prompting the developer to explicitly review and upgrade.

### ADR-003: HMAC Worker Authentication
* **Status:** Approved
* **Context:** The host worker executes shell commands and writes files. It must not accept unauthenticated calls from Docker or local sockets.
* **Decision:** Authenticate control plane requests to the worker via SHA256 request signatures containing timestamps, seen nonce replay protection, and support for HMAC secret rotation.
* **Consequences:** Rejects stale timestamps (age > 5 mins) and replayed nonces.

### ADR-004: Codex App Server Stdio Integration
* **Status:** Approved
* **Context:** VS Code workflow requires threads, continuing sessions, streaming events, and tool execution without scraping or automating VS Code extensions directly.
* **Decision:** Launch and communicate with local Codex App Server via JSON-RPC stdio subprocess pipelines.
* **Consequences:** Eliminates external ports and scraped elements.

### ADR-005: Logical Model-Tier Resolution
* **Status:** Approved
* **Context:** Models catalog changes and logical capabilities should not be tightly coupled to hardcoded model IDs in code.
* **Decision:** Define logical routing aliases (`codex.economy`, `codex.balanced`, `codex.max`) matching logical tiers (Luna, Terra, Sol) and resolve active models dynamically from the catalog.
* **Consequences:** Decouples policies from specific model releases.

### ADR-006: Git Worktree Attempt Isolation
* **Status:** Approved
* **Context:** Automated model editing can corrupt workspaces or leak dirty states.
* **Decision:** Isolate every write-capable task attempt inside a dedicated sibling Git worktree (`~/.cognito/worktrees/<repo-id>/<task-id>/attempt-XX/`) cloned from the initial base commit.
* **Consequences:** Developer's primary checkout is never modified.

### ADR-007: PostgreSQL Authoritative State
* **Status:** Approved
* **Context:** Complex orchestration, retry tracking, and audits require strong ACID storage.
* **Decision:** Declare PostgreSQL (schema `cognito`) as the single authoritative source of state for all tasks, decisions, attempts, and metadata.
* **Consequences:** Reliable state reconstruction and crash recovery.

### ADR-008: Transactional Outbox Pattern
* **Status:** Approved
* **Context:** Writing to both database and Redis can lead to partial failures and inconsistent events.
* **Decision:** Save task state changes and write to `cognito.outbox_events` in a single PostgreSQL transaction. Push events to Redis asynchronously.
* **Consequences:** Bulletproof delivery guarantees even during Redis outages.

### ADR-009: Qdrant Semantic-Memory Boundaries
* **Status:** Approved
* **Context:** Semantic retrieval of document context is useful but must not block core execution.
* **Decision:** Use Qdrant solely as semantic memory (indexing AGENTS.md, failures, etc.) with non-blocking graceful fallback.
* **Consequences:** Routing and code execution continue normally even if Qdrant goes offline.

### ADR-010: Escalation and Fresh-Attempt Strategy
* **Status:** Approved
* **Context:** A weak model's attempt can fail tests. Continuing directly on top of its broken files can cause drift.
* **Decision:** If a model-related verification failure occurs, start a fresh attempt worktree from the base commit, passing the previous failure logs and patch as read-only context.
* **Consequences:** Empowers stronger models to repair rather than inherit corruption.

### ADR-011: MCP Recursion Prevention
* **Status:** Approved
* **Context:** Codex calling MCP tools must not trigger another recursive Codex turn infinitely.
* **Decision:** Validate `correlation_id`, `origin`, and `execution_depth` on all tool calls, rejecting beyond depth limits.
* **Consequences:** Guarantees termination.

### ADR-012: Observability and Sensitive-Data Handling
* **Status:** Approved
* **Context:** Structured JSON logs are vital but must not leak tokens, secrets, or source selections.
* **Decision:** Implement JSON structured formatters with automatic context vars correlation and recursive regex-based key redaction.
* **Consequences:** Safe, high-utility logs.

---

## 🚀 Operating & Setup Guide

### 1. Database Migrations
Apply DDL tables and schema setups in SQLite/PostgreSQL:
```bash
# Run schema and tables migrations
python3 -m app.core.database migrate
```

### 2. Starting the Control Plane
Deploy the backend control plane via Docker Compose:
```bash
docker compose up -d cognito-backend
```

### 3. Installing & Running the Host Worker
Install dependencies and run uvicorn locally:
```bash
cd very-simplified-stack/cognito-worker
pip install -r requirements.txt
PYTHONPATH=.:../cognito-backend uvicorn worker_app.main:app --host 127.0.0.1 --port 8765
```

### 4. Enable Systemd User Service (Arch/CachyOS)
To run the worker persistently in the background:
```bash
mkdir -p ~/.config/systemd/user/
cp cognito-worker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now cognito-worker
```

### 5. Running Evaluations & Shadow Mode
Run the offline evaluation benchmark:
```bash
cd very-simplified-stack
# Standard report
PYTHONPATH=cognito-backend:evals python3 -m evals.router run

# Shadow mode
PYTHONPATH=cognito-backend:evals python3 -m evals.router run --shadow
```

---

## 🛡️ Robust Failures & Graceful Degradation

### When Ollama is Offline
* Classifier falls back gracefully to a deterministic routing policy, mapping standard renames to Luna, and features to Terra, without crashing.

### When Codex is Unauthenticated
* Discovered models catalog reports logical tiers as unavailable. Task creation fails explicitly telling the developer to authenticate Codex first.

### When Qdrant is Offline
* Points indexing fails gracefully, logging a warning but continuing execution, and MCP search returns empty lists without interrupting the task.
