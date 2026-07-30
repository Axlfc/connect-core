# Finding Detail Fields

Every valid finding produced by Codex Security must conform to the following schema structure:

- `cwe`: String representation of the Common Weakness Enumeration, e.g., `"CWE-79"`.
- `file_path`: String representing the relative file path to the scanned root.
- `line`: Integer line number where the finding resides.
- `severity`: One of `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`.
- `description`: Actionable detail describing the vulnerability, its cause, and impact.
- `fingerprint`: Unique hash of the finding used for deduplication and triage state persistence.
