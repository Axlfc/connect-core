# AUDIT 13: DEPENDENCIES AND LIBRARIES
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Use of Standard Tools** | The project uses industry-standard package managers (`pip` for Python, `npm`/`pnpm` for Node.js), which facilitates dependency management and auditing. |
| ✗ | **Unpinned Dependencies** | **CRITICAL:** Multiple `requirements.txt` files and Dockerfiles **do not pin versions** of the dependencies they install. This leads to non-reproducible builds and creates a significant risk that a new version of a library introduces a vulnerability or a breaking change. |
| ✗ | **Lack of Vulnerability Scanning** | There is no evidence that any tool is used to scan dependencies (e.g., `pip-audit`, `npm audit`, `snyk`, `trivy`) for known vulnerabilities (CVEs). |
| ⚠️ | **Use of "Nightly" Dependencies** | `Dockerfile.comfyui` installs "nightly" versions of PyTorch. These versions are unstable by definition, are not intended for production, and may contain undiscovered bugs or vulnerabilities. |
| ⚠️ | **Missing `package-lock.json`** | The `ollama-proxy` (Node.js) service does not include a `package-lock.json` file in the repository. This means exact versions of transitive dependencies are not guaranteed, undermining reproducibility. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Centralized Management:**
    *   Each component (e.g., `voice-gateway`, `ollama-proxy`) has its own dependency file (`requirements.txt`, `package.json`), which is a good practice that isolates environments.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **DEP-01** | **CRITICAL** | **Unpinned Versions in `requirements.txt`** | The `voice-gateway/requirements.txt` file lists dependencies like `fastapi` or `redis` without specifying a version. `pip install -r requirements.txt` will install the latest version available at that time, which can vary day to day, making it impossible to guarantee a stable and secure build. |
| **DEP-02** | **HIGH** | **Use of Flexible Versioning (`^`) in `package.json`** | `ollama-proxy/package.json` uses `^` for its dependencies (e.g., `"express": "^4.18.2"`). While this prevents major changes (version 5.x), it still allows minor updates (e.g., 4.19.0) that could introduce regressions or vulnerabilities. The absence of a `package-lock.json` exacerbates this problem. |
| **DEP-03** | **HIGH** | **"Nightly" Dependencies in `Dockerfile.comfyui`** | The Dockerfile installs PyTorch directly from a `nightly` index. This is unacceptable for a production environment, as these builds have no guarantee of stability or security. |

---

### ⚠️ Warnings/Recommendations

1.  **License Audit:**
    *   There is no process to audit dependency licenses. This could pose a legal risk if a library with a restrictive license (such as AGPL) were used without complying with its terms.

2.  **Operating System Dependencies:**
    *   Dockerfiles install OS dependencies via `apt-get` or `apk`. These dependencies should also be audited and, if possible, pinned to a specific version if the package manager allows it.

---

### 🔧 Suggested Solutions

1.  **For DEP-01 (Pin Versions in `requirements.txt` - CRITICAL):**
    *   **Solution:** Use a tool like `pip-tools` to manage Python dependencies robustly.
        1.  **Create a `requirements.in` file:**
            ```
            # voice-gateway/requirements.in
            fastapi
            uvicorn
            httpx
            redis
            python-multipart
            ```
        2.  **Generate `requirements.txt`:**
            ```bash
            # Install pip-tools
            pip install pip-tools
            # Compile the requirements file
            pip-compile voice-gateway/requirements.in > voice-gateway/requirements.txt
            ```
        3.  **Result:** The generated `requirements.txt` will contain exact versions of all dependencies and their transitive dependencies, with hashes to verify integrity.
            ```
            # via -r requirements.in
            fastapi==0.109.2
            # ... (all other dependencies with exact versions and hashes)
            ```

2.  **For DEP-02 (Pin Versions in `package.json`):**
    *   **Solution:**
        1.  **Remove the `^`:** Replace `^x.y.z` with `x.y.z` for all dependencies in `package.json`.
        2.  **Generate and Commit the Lock File:** Run `npm install` locally and add the resulting `package-lock.json` file to the repository. This will ensure that the exact same versions of all dependencies are always installed.

3.  **For DEP-03 (Remove "Nightly" Dependencies):**
    *   **Solution:** Modify `Dockerfile.comfyui` to use the latest **stable version** of PyTorch that is compatible with the target hardware.
        ```diff
        # In Dockerfile.comfyui
        -      --index-url https://download.pytorch.org/whl/nightly/cu128
        +      --index-url https://download.pytorch.org/whl/cu128
        ```
    *   Pinning the PyTorch version to a specific number is even better.

4.  **Implement Vulnerability Scanning:**
    *   **Solution:** Integrate scanning tools into the CI/CD process.
        *   **For Python:** Add a step that runs `pip-audit`.
        *   **For Node.js:** Add a step that runs `npm audit --audit-level=high`.
        *   **For Docker Images:** Use a tool like `Trivy` or `Grype` to scan built images for vulnerabilities in both OS and application dependencies.
