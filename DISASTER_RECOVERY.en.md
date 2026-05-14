# Disaster Recovery Guide
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/DISASTER_RECOVERY.zh-cn.md)


## 1. Introduction

This document describes the backup strategy and restoration procedures for the `connect-core` stack. The goal is to ensure the integrity and availability of critical data in case of system failure, data corruption, or any other catastrophic event.

The strategy is based on the use of **Duplicati**, an open-source backup client that runs as a container within the stack.

## 2. Access to Duplicati

The Duplicati web interface is available at the following `URL`:

- **URL:** `http://duplicati.localhost` (or the domain you have configured)
- **Access:** Protected by Authelia. You must log in with your credentials.

## 3. Configuring a Backup Job

Below is the detailed procedure to create a backup job for the system's most critical data.

### Step 1: Add a new backup

1.  In the Duplicati interface, click **"Add backup"**.
2.  Select **"Configure a new backup"** and click "Next".

### Step 2: General configuration

1.  **Name:** Assign a descriptive name (e.g., "connect-core Critical Data").
2.  **Encryption:** It is strongly recommended to **enable encryption**. Select "AES-256 encryption, built-in" and generate a secure password. **Save this password in a safe place! Without it, you will not be able to restore your data.**
3.  Click "Next".

### Step 3: Backup destination

1.  **Storage Type:** Choose where you want to store your backups. Duplicati supports a wide variety of destinations, such as `SFTP`, `WebDAV`, `Google Drive`, `Amazon S3`, etc.
2.  **Local folder or drive:** For this example, we will use a local directory on the `host`. The path inside the container pointing to a directory on the `host` is `/backups`.
    - **Path:** `/backups`
3.  Configure credentials or connection information needed for your chosen destination.
4.  Click **"Test connection"** to verify that Duplicati can access the destination.
5.  Click "Next".

### Step 4: Source data

1.  This is the most important part. Here you will select the directories you want to backup. Docker service data is located in the `/source` directory inside the Duplicati container.
2.  Expand the directory tree and select the following volumes, which contain the most critical data:
    - `postgres_storage`
    - `n8n_storage`
    - `forgejo_data`
    - `redis_data`
    - `qdrant_storage`
    - `matrix_data`
    - `authelia` (for user configuration)
3.  Click "Next".

### Step 5: Schedule

1.  Define how often you want backups to run. A **daily** backup is recommended.
2.  Select a time when the system has low load (e.g., 3:00 AM).
3.  Click "Next".

### Step 6: Backup options

1.  **Remote volume size:** Adjust the size of the backup volumes. A value of `50 MB` is a good starting point.
2.  **Backup retention:** Define how long you want to keep backups. It is recommended to choose **"Keep a specific number of backups"** and set a value like `14` to have two weeks of history.
3.  Click **"Save"**.

## 4. Restoration Procedure

In case you need to restore data, follow these steps:

### Step 1: Stop services

Before restoring, it is crucial to stop all services to avoid data inconsistencies.

```bash
./stop.sh
```

### Step 2: Access restoration in Duplicati

1.  Open the Duplicati interface.
2.  Click on the backup job you want to restore.
3.  Click **"Restore"**.

### Step 3: Select files to restore

1.  Select the backup date you want to restore.
2.  You can restore all files or select specific directories. For a full recovery, select all directories.
3.  Click "Continue".

### Step 4: Restoration options

1.  **Restore to original location:** Select this option to restore files to their original directories.
2.  **Overwrite:** Select "Overwrite" to replace any existing (corrupted) files with the version from the backup.
3.  Click **"Restore"**.

### Step 5: Verify and restart services

1.  Once the restoration is complete, verify that files have been correctly restored to the Docker volumes on the `host`.
2.  Restart the `connect-core` stack.

```bash
./start.sh
```

## 5. Conclusion

This guide provides the fundamental steps to secure and restore `connect-core` data. It is the system administrator's responsibility to ensure that backups are correctly configured, run regularly, and tested periodically.
