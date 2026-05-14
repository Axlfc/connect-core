# 审计 13：依赖项与库
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **使用标准工具** | 项目使用了行业标准的包管理器（Python 使用 `pip`，Node.js 使用 `npm`/`pnpm`），这便利了依赖项的管理和审计。 |
| ✗ | **未固定依赖版本 (Unpinned)** | **关键：** 多个 `requirements.txt` 文件和 Dockerfile **未固定**其安装的依赖项版本。这导致构建不可复现，并带来显著风险：新版本的库可能会引入漏洞或破坏性更改。 |
| ✗ | **缺少漏洞扫描** | 没有证据表明使用了任何工具（如 `pip-audit`, `npm audit`, `snyk`, `trivy`）来扫描依赖项中的已知漏洞 (CVE)。 |
| ⚠️ | **使用“Nightly”版本依赖** | `Dockerfile.comfyui` 安装了 PyTorch 的 "nightly" 版本。顾名思义，这些版本是不稳定的，并非为生产环境设计，可能包含未发现的 Bug 或漏洞。 |
| ⚠️ | **缺少 `package-lock.json`** | `ollama-proxy` (Node.js) 服务在仓库中未包含 `package-lock.json` 文件。这意味着无法保证间接依赖项的准确版本，破坏了可复现性。 |

---

## 2. 详细发现

### ✓ 优点

1.  **集中化管理：**
    *   每个组件（如 `voice-gateway`, `ollama-proxy`）都有自己的依赖文件（`requirements.txt`, `package.json`），这是一种隔离环境的良好实践。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **DEP-01** | **关键** | **`requirements.txt` 中未固定版本** | `voice-gateway/requirements.txt` 列出了 `fastapi` 或 `redis` 等依赖项，但未指定版本。`pip install -r requirements.txt` 将安装当时的最新版本，该版本可能每天都在变化，导致无法保证构建的稳定性和安全性。 |
| **DEP-02** | **高** | **在 `package.json` 中使用灵活版本号 (`^`)** | `ollama-proxy/package.json` 对其依赖项使用了 `^`（例如 `"express": "^4.18.2"`）。虽然这能防止重大更改（版本 5.x），但仍允许可能引入回归或漏洞的次要更新（如 4.19.0）。缺少 `package-lock.json` 加剧了这一问题。 |
| **DEP-03** | **高** | **`Dockerfile.comfyui` 中的“Nightly”依赖** | Dockerfile 直接从 `nightly` 索引安装 PyTorch。这对于生产环境来说是不可接受的，因为这些构建版本没有任何稳定性和安全性保证。 |

---

### ⚠️ 警告/建议

1.  **许可证 (License) 审计：**
    *   没有审计依赖项许可证的流程。如果使用了带有严格许可证（如 AGPL）的库而未遵守其条款，可能会带来法律风险。

2.  **操作系统依赖项：**
    *   Dockerfile 通过 `apt-get` 或 `apk` 安装操作系统依赖。如果包管理器允许，这些依赖也应进行审计，并尽可能固定到特定版本。

---

### 🔧 建议的解决方案

1.  **针对 DEP-01（在 `requirements.txt` 中固定版本 - 关键）：**
    *   **解决方案：** 使用 `pip-tools` 之类的工具来稳健地管理 Python 依赖。
        1.  **创建 `requirements.in` 文件：**
            ```
            # voice-gateway/requirements.in
            fastapi
            uvicorn
            httpx
            redis
            python-multipart
            ```
        2.  **生成 `requirements.txt`：**
            ```bash
            # 安装 pip-tools
            pip install pip-tools
            # 编译需求文件
            pip-compile voice-gateway/requirements.in > voice-gateway/requirements.txt
            ```
        3.  **结果：** 生成的 `requirements.txt` 将包含所有依赖项及其间接依赖项的准确版本和用于验证完整性的哈希值。
            ```
            # via -r requirements.in
            fastapi==0.109.2
            # ... (带有准确版本和哈希的所有其他依赖项)
            ```

2.  **针对 DEP-02（在 `package.json` 中固定版本）：**
    *   **解决方案：**
        1.  **移除 `^`：** 在 `package.json` 中将所有依赖项的 `^x.y.z` 替换为 `x.y.z`。
        2.  **生成并提交 Lock 文件：** 在本地运行 `npm install` 并将生成的 `package-lock.json` 文件添加到仓库。这将确保始终安装所有依赖项的完全相同的版本。

3.  **针对 DEP-03（移除“Nightly”依赖）：**
    *   **解决方案：** 修改 `Dockerfile.comfyui` 以使用与目标硬件兼容的最新**稳定版本**的 PyTorch。
        ```diff
        # 在 Dockerfile.comfyui 中
        -      --index-url https://download.pytorch.org/whl/nightly/cu128
        +      --index-url https://download.pytorch.org/whl/cu128
        ```
    *   将 PyTorch 版本固定到具体数值则更好。

4.  **实施漏洞扫描：**
    *   **解决方案：** 在 CI/CD 流程中集成扫描工具。
        *   **针对 Python：** 添加运行 `pip-audit` 的步骤。
        *   **针对 Node.js：** 添加运行 `npm audit --audit-level=high` 的步骤。
        *   **针对 Docker 镜像：** 使用 `Trivy` 或 `Grype` 等工具扫描构建的镜像，检查操作系统和应用依赖项中的漏洞。
