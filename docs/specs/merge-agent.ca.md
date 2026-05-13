# Merge Agent Specification
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/specs/merge-agent.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/specs/merge-agent.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/specs/merge-agent.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/specs/merge-agent.zh-cn.md)


## 1. Architecture

The Merge Agent is a standalone service that listens for webhooks from Forgejo. It is designed to be a stateless service, with all state managed through Forgejo pull requests and repository data.

### Components:

- **VCS (Version Control Service):** An internal service that acts as an abstraction layer for the Forgejo API. This service will be responsible for all communication with Forgejo, including fetching repository data, creating comments, and updating pull request statuses.
- **Merge Agent:** The core service that contains the business logic for determining if a pull request can be automatically merged. It receives webhook events, interacts with the VCS service, and triggers the Runner service.
- **Runner/Executor:** A service responsible for executing builds, tests, and other checks in a sandboxed environment. This service will be triggered by the Merge Agent and will report back the results.
- **Artifacts Storage:** A shared volume or S3-compatible storage for persisting artifacts such as merge reports, diffs, and logs.

### Diagram:

```
+----------+      +------------------+      +-------------+
| Forgejo  |----->|   Merge Agent    |----->|   Runner    |
+----------+      +------------------+      +-------------+
      ^                   |                       |
      |                   v                       v
      +-----------+ VCS Service +--------> Artifacts Storage
```

## 2. Forgejo Integration

The Merge Agent relies on Forgejo webhooks to initiate its workflow.

### Required Webhook Events:

- **`pull_request`:** Triggered when a pull request is created, updated, or synchronized. The agent will listen for the `opened`, `edited`, and `synchronize` actions.
- **`push`:** Triggered when a push is made to the target branch of an open pull request. This will trigger a re-evaluation of the PR.
- **`pull_request_comment`:**  (Optional) Can be used to trigger a merge attempt manually with a specific command in a comment (e.g., `/merge`).

### Webhook Verification:

- All incoming webhooks will be verified using a shared secret configured in both Forgejo and the Merge Agent. The signature of the payload will be checked to ensure it originated from Forgejo.

### API Usage:

- **Get Pull Request Diff:** Fetch the diff of the pull request to analyze the changes.
- **Get Commits:** Retrieve the list of commits in the pull request.
- **Get File Contents:** Read the contents of specific files (e.g., configuration files, lock files).
- **Create Comment:** Post the merge report on the pull request.
- **Update Status Checks:** Update the status of the pull request with the results of the merge attempt (e.g., `pending`, `success`, `failure`).

## 3. Merge Resolution Policy

### Hard Gates:

The following checks must pass for a merge to be considered:

1.  **Build:** The code must compile successfully.
2.  **Typecheck:** Static type checking must pass.
3.  **Tests:** All unit and integration tests must pass.

### Heuristics for Conflicts:

- **Prioritize Functional Invariants:** The agent will be configured with a set of rules that define the core functional invariants of the application. Changes that violate these invariants will be rejected.
- **Source of Truth vs. Derived State:** When a conflict involves both a source of truth (e.g., a data model) and a derived state (e.g., a cached view of that model), the agent will prioritize the changes to the source of truth.
- **Adapt to Target Contract:** The agent will analyze the target branch to understand its current "contract" (e.g., API signatures, data schemas). The incoming changes will be adapted to match the target contract.

### Uncertainty Handling:

- If the agent is uncertain about how to resolve a conflict, it will **not** merge the pull request. Instead, it will generate a detailed report outlining the conflict and a suggested plan for manual resolution.

## 4. Artifacts

- **`merge-report.md`:** A Markdown file detailing the outcome of the merge attempt.
- **`patch.diff`:** The diff that was applied.
- **`logs.txt`:** The raw logs from the build and test execution.
