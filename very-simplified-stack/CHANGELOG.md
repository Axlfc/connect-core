# 📝 Changelog: Cognito-Codex Intelligent Development Router

All notable changes implemented for the Cognito-Codex Intelligent Router are documented here.

## [1.0.0] - 2025-06-25

### Added
- **Host-Side Worker (`cognito-worker`)**: Added a Python 3.12 FastAPI microservice executing tasks in clean, isolated Git worktrees.
- **VS Code Extension (`vscode-cognito-router`)**: Developed a companion extension with task previews, manual overrides, and a rich card interface.
- **Granular Trust Store**: Replaced binary trust with custom resource-specific permissions (`read`, `write`, `shell`, `network`, `git_commit`, `git_push`, `extensions`, `secrets`, `destructive_operations`).
- **Deterministic Shell Policy Engine**: Introduced robust compound shell parsing, tokenizer classification, and unconditional deny rules (blocking `sudo`, `rm -rf`, force pushes).
- **Ollama structured Classifier**: Created Pydantic-validated JSON task classification on Ollama.
- **Transactional Outbox Pattern**: Implemented outbox pattern on Postgres tables for task events to avoid partial writes.
- **Cognito MCP Server**: Added optional Model Context Protocol with features like semantic repository searches and execution recursion check.
- **Structured JSON Logging**: Implemented contextvars correlation and sensitive keys redaction.
- **Evaluation Suite**: Developed an offline/shadow benchmark tool with exact metrics.

### Changed / Fixed
- Fixed `SemanticOrchestrator` caller mismatches (`process_request` alias).
- Fixed extension loading on startup, and dynamic registry integrations on `BackendRouter`.
- Upgraded path containment checks using canonical resolution and `os.path.commonpath`.
