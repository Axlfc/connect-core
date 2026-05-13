# Archaeology Agent Specification
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/docs/specs/archaeology.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/docs/specs/archaeology.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/docs/specs/archaeology.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/docs/specs/archaeology.zh-cn.md)


## 1. Architecture

The Archaeology Agent is a service designed to analyze the Git history of a repository to identify regressions and lost features. It can be triggered manually or on a schedule.

### Components:

- **Archaeology Service:** The core service that orchestrates the analysis. It fetches the Git history from Forgejo, iterates through commits, and triggers the Runner service for each commit.
- **VCS (Version Control Service):** The same service used by the Merge Agent, providing an abstraction layer for the Forgejo API.
- **Runner/Executor:** The same service used by the Merge Agent, responsible for executing tests and other checks in a sandboxed environment.
- **Artifacts Storage:** A shared volume or S3-compatible storage for persisting the results of the analysis.

### Diagram:

```
+-------------------+      +-------------+
| Archaeology Svc   |----->|   Runner    |
+-------------------+      +-------------+
      |                          |
      v                          v
+-------------+      +---------------------+
| VCS Service |----->|  Artifacts Storage  |
+-------------+      +---------------------+
      ^
      |
+----------+
| Forgejo  |
+----------+
```

## 2. Execution Design

### Commit Selection:

The analysis can be configured to run on:

- **All merge commits:** To analyze the history of integrated features.
- **All tagged commits:** To analyze the history of releases.
- **The last N commits:** To perform a quick analysis of recent changes.

### Execution Flow:

1.  **Select Commits:** The Archaeology service selects a range of commits to analyze based on the configured strategy.
2.  **Execute Suites per Commit:** For each selected commit, the service checks out the code and triggers the Runner to execute a predefined suite of tests.
3.  **Detect Pass/Fail Transitions:** The service records the test results for each commit and identifies transitions from a `pass` state to a `fail` state.
4.  **Directed Bisect for Culpable Commit:** When a regression is detected, the service performs a `git bisect` to pinpoint the exact commit that introduced the regression.

## 3. Feature Fingerprints

To detect lost features, the Archaeology service uses a "feature fingerprint" mechanism.

### Minimum Schema:

- **`anchors`:** A list of strings or regular expressions that identify a feature. These can be:
    - **`exports`:** Names of exported functions or classes.
    - **`routes`:** API endpoint paths.
    - **`tests`:** Names of specific tests.
    - **`strings`:** Unique strings that are part of the feature's UI or logs.
- **`score`:** The agent will calculate a score for each feature at each commit, based on the presence of its anchors. The score can be:
    - **`present`:** All anchors are found.
    - **`partial`:** Some anchors are found.
    - **`missing`:** No anchors are found.

## 4. Output

- **`regression-map.json`:** A JSON file that maps each regression to the commit that introduced it.
- **`feature-loss-report.md`:** A Markdown report detailing any features that were detected as "lost" during the analysis.
- **`FEATURES_PENDING.md`:** A backlog of features that were identified as missing or partially implemented. This can also be configured to create issues in Forgejo directly.
