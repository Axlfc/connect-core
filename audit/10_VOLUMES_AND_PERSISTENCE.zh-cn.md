# 审计 10：卷管理与持久性
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.ca.md)


**日期：** 2024-07-25
**分析师：** Jules

## 1. 发现摘要

| 状态 | 领域 | 发现摘要 |
| :--- | :--- | :--- |
| ✓ | **持久化策略** | 为所有状态数据（`postgres_storage`, `n8n_storage` 等）使用 Docker 命名卷的策略是**正确且稳健的**。它将数据的生命周期与容器的生命周期分离开来。 |
| ✓ | **备份意图** | `duplicati` 服务和 `duplicati-job-template.json` 的存在表明了**实施备份的明确意图**，这对于数据的弹性至关重要。 |
| ⚠️ | **卷权限** | `inspect_volumes.sh` 脚本需要 `sudo` 权限来计算卷的大小 (`du -sh`)。这表明宿主机上的卷目录权限可能未与系统用户正确对齐，这可能会导致运行时权限问题。 |
| ✗ | **未实施备份策略** | 系统**缺乏自动化且功能齐全的备份策略**。`duplicati-job-template.json` 仅仅是一个模板；没有任何脚本或机制能自动在 Duplicati 中配置备份作业，使得该过程完全依赖手动操作且容易出错。 |
| ✗ | **缺少恢复程序** | 没有记录或测试过灾难恢复程序。关于恢复的唯一参考是 `inspect_volumes.sh` 输出中的 `docker` 命令，这对于**生产环境来说是远远不够的**。 |

---

## 2. 详细发现

### ✓ 优点

1.  **使用命名卷：**
    *   `docker-compose.yml` 为每个有状态服务显式定义了命名卷。与用于数据的 `bind` 挂载相比，这是一种最佳实践，因为卷由 Docker 引擎管理，更具移植性且更易于处理。

2.  **定义良好的备份模板：**
    *   `backups/duplicati-job-template.json` 文件定义了一个稳固的备份作业：
        *   **源路径清晰：** 正确识别了要备份的关键目录（`./shared`, `./data`, `./models`）。
        *   **启用加密：** 指定了 `encryption-module: aes`，这对于备份安全至关重要。
        *   **每日调度：** `Schedule: "@daily"` 是大多数用例的一个合理起点。

### ✗ 发现的问题

| ID | 严重程度 | 问题 | 影响 |
| :- | :--- | :--- | :--- |
| **V-01** | **高** | **手动备份流程** | 缺乏配置 Duplicati 的自动化手段。管理员必须：1) 启动堆栈。2) 访问 Duplicati UI。3) 创建新的备份作业。4) 配置目的地。5) 配置加密密码。6) 选择源目录。这一手动过程容易出现配置错误，且极易被遗忘。 |
| **V-02** | **高** | **缺失灾难恢复计划** | 如果宿主服务器发生灾难性故障，没有分步指南说明如何在新主机上恢复服务和数据。如果恢复操作不当，这将显著增加恢复时间目标 (RTO) 并带来数据丢失风险。 |
| **V-03** | **中** | **潜在的卷权限问题** | 在诊断脚本中需要 `sudo` 来查看卷大小这一事实是一个“代码异味 (code smell)”。它表明容器内进程的 UID/GID 可能与宿主机上的文件所有权不匹配，这是生产环境中“权限被拒绝”错误的常见原因。 |

---

### ⚠️ 警告/建议

1.  **数据库备份：**
    *   目前的备份依赖于复制数据库卷文件 (`postgres_storage`)。这被称为“冷备份”或文件系统备份。为了确保数据一致性，最佳实践是使用数据库特定的工具（如 `pg_dump`）。如果在备份过程中正在进行写入，当前的备份可能会抓取到处于不一致状态的数据库。

2.  **恢复测试：**
    *   备份计划在恢复过程经过测试之前是不完整的。目前没有任何证据表明进行过恢复测试。

---

### 🔧 建议的解决方案

1.  **针对 V-01（自动化 Duplicati 配置）：**
    *   **解决方案：** 为 Duplicati 创建一个初始化脚本。
        1.  **创建脚本 (`scripts/init_duplicati.sh`)：** 该脚本将使用 Duplicati API 或其 CLI (`duplicati-cli`) 在首次启动时自动配置备份作业。
        2.  **脚本逻辑：**
            *   等待 Duplicati API 可用。
            *   从 `.env` 文件读取环境变量（例如 `DUPLICATI_DESTINATION`, `DUPLICATI_PASSPHRASE`）。
            *   使用 `sed` 或类似工具替换 `duplicati-job-template.json` 中的占位符。
            *   将生成的 JSON 发送 (POST) 到 Duplicati API 端点以创建/更新作业。
        3.  **运行脚本：** 将此脚本作为 `docker-compose` 服务在启动时运行一次，或将其作为 `start.sh` 脚本的一部分。

2.  **针对 V-02（创建恢复计划）：**
    *   **解决方案：** 创建 `DISASTER_RECOVERY.md` 文档。
        *   **文档内容：**
            *   **前提条件：**（例如：安装了 Docker 的新主机）。
            *   **第 1 步：还原备份：** 关于如何使用 Duplicati UI 或 CLI 将数据从目标存储还原到临时目录的详细说明。
            *   **第 2 步：重新初始化堆栈：** 如何克隆仓库，运行 `init_env.sh` 和 `setup-permissions.sh`。
            *   **第 3 步：导入还原的数据：** 使用 `docker cp` 或卷挂载命令将还原的数据移动到新的 Docker 卷中。
            *   **第 4 步：验证：** 如何验证服务已正确启动且数据完好无损。
        *   **测试：** 此程序必须至少测试一次，以确保其按预期工作。

3.  **针对 V-03（修复权限）：**
    *   **解决方案：** 扩展并强制使用 `setup-permissions.sh`。
        *   确保 `setup-permissions.sh` 脚本为**所有**需要的卷创建宿主机目录，而不仅仅是日志。
        *   在所有 `docker-compose.yml` 服务和 `setup-permissions.sh` 脚本中一致地使用来自 `.env` 文件的 `PUID` 和 `PGID` 变量，以便权限匹配。
