# Scan Artifacts Conventions

This document specifies the standard locations and file formats for artifacts produced by Codex Security.

## Output Directory Structure

The `outputDir` specified during the scan execution contains the following artifacts:

- `result.json`: The complete raw JSON containing all detected candidates and finding occurrences.
- `result.sarif`: The standard sealed SARIF version of the findings for ingestion into platforms like GitHub or GitLab.
- `result.csv`: A flattened CSV file containing a list of findings with CWE, path, line, severity, and description.
- `session_cost.json`: Real-time tracked USD and token usage metrics.
