# 灾难恢复指南 (Disaster Recovery)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.ca.md)


## 1. 引言

本文档介绍了 `connect-core` 堆栈的备份策略和恢复程序。目标是确保在系统故障、数据损坏或任何其他灾难性事件发生时，关键数据的完整性和可用性。

该策略基于 **Duplicati** 的使用，这是一个开源备份客户端，作为容器在堆栈内运行。

## 2. 访问 Duplicati

Duplicati 的 Web 界面可通过以下 `URL` 访问：

- **URL:** `http://duplicati.localhost` (或您配置的域名)
- **访问:** 由 Authelia 保护。您必须使用您的凭据登录。

## 3. 配置备份作业

以下是为系统最关键数据创建备份作业的详细步骤。

### 第 1 步：添加新的备份

1.  在 Duplicati 界面中，点击 **"Add backup"**。
2.  选择 **"Configure a new backup"** 并点击 "Next"。

### 第 2 步：常规配置

1.  **Name:** 输入一个具描述性的名称（例如 "connect-core Critical Data"）。
2.  **Encryption:** 强烈建议**启用加密**。选择 "AES-256 encryption, built-in" 并生成一个强密码。**请将此密码保存在安全的地方！没有它，您将无法恢复数据。**
3.  点击 "Next"。

### 第 3 步：备份目的地

1.  **Storage Type:** 选择您想要存储备份的位置。Duplicati 支持多种目的地，如 `SFTP`、`WebDAV`、`Google Drive`、`Amazon S3` 等。
2.  **Local folder or drive:** 在本示例中，我们将使用 `宿主机 (host)` 上的本地目录。指向宿主机目录的容器内路径为 `/backups`。
    - **Path:** `/backups`
3.  为您选择的目的地配置所需的凭据或连接信息。
4.  点击 **"Test connection"** 以验证 Duplicati 是否可以访问该目的地。
5.  点击 "Next"。

### 第 4 步：源数据

1.  这是最核心的部分。在这里，您将选择想要备份的目录。Docker 服务数据位于 Duplicati 容器内的 `/source` 目录中。
2.  展开目录树并选择以下卷 (Volumes)，它们包含最关键的数据：
    - `postgres_storage`
    - `n8n_storage`
    - `forgejo_data`
    - `redis_data`
    - `qdrant_storage`
    - `matrix_data`
    - `authelia` (用于用户配置)
3.  点击 "Next"。

### 第 5 步：调度

1.  定义备份运行的频率。建议**每天**备份。
2.  选择系统负载较低的时间（例如凌晨 3:00）。
3.  点击 "Next"。

### 第 6 步：备份选项

1.  **Remote volume size:** 调整备份卷的大小。`50 MB` 是一个不错的起始值。
2.  **Backup retention:** 定义您想要保留备份的时间。建议选择 **"Keep a specific number of backups"** 并设置一个值（如 `14`），以保留两周的历史记录。
3.  点击 **"Save"**。

## 4. 恢复程序

如果您需要恢复数据，请按照以下步骤操作：

### 第 1 步：停止服务

在恢复之前，必须停止所有服务以避免数据不一致。

```bash
./stop.sh
```

### 第 2 步：在 Duplicati 中进入恢复界面

1.  打开 Duplicati 界面。
2.  点击您想要恢复的备份作业。
3.  点击 **"Restore"**。

### 第 3 步：选择要恢复的文件

1.  选择您想要恢复的备份日期。
2.  您可以恢复所有文件或选择特定目录。如需完全恢复，请选择所有目录。
3.  点击 "Continue"。

### 第 4 步：恢复选项

1.  **Restore to original location:** 选择此选项将文件恢复到其原始目录。
2.  **Overwrite:** 选择 "Overwrite" 以使用备份版本替换任何现有的（损坏的）文件。
3.  点击 **"Restore"**。

### 第 5 步：验证并重启服务

1.  恢复完成后，验证文件是否已正确还原到宿主机上的 Docker 卷中。
2.  重启 `connect-core` 堆栈。

```bash
./start.sh
```

## 5. 结论

本指南提供了保护和恢复 `connect-core` 数据的基本步骤。系统管理员有责任确保备份配置正确、定期运行并定期进行测试。
