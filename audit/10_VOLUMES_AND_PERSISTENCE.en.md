# AUDIT 10: VOLUME MANAGEMENT AND PERSISTENCE
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.zh-cn.md)


**Date:** 2024-07-25
**Analyst:** Jules

## 1. Summary of Findings

| Status | Area | Summary of Findings |
| :--- | :--- | :--- |
| ✓ | **Persistence Strategy** | The strategy of using Docker named volumes for all state data (`postgres_storage`, `n8n_storage`, etc.) is **correct and robust**. It separates the data life cycle from that of the containers. |
| ✓ | **Backup Intent** | The presence of a `duplicati` service and a `duplicati-job-template.json` demonstrates a **clear intent to implement backups**, which is fundamental for data resilience. |
| ⚠️ | **Volume Permissions** | The `inspect_volumes.sh` script requires `sudo` to calculate volume sizes (`du -sh`). This suggests that volume directory permissions on the host may not be correctly aligned with system users, which could lead to runtime permission issues. |
| ✗ | **Backup Strategy Not Implemented** | The system **lacks an automated and functional backup strategy**. The `duplicati-job-template.json` is only a template; there is no script or mechanism that automatically configures the backup job in Duplicati, leaving the process entirely manual and error-prone. |
| ✗ | **No Recovery Procedures** | There is no documented or tested disaster recovery procedure. The only references to restoration are `docker` commands in the `inspect_volumes.sh` output, which is **insufficient for a production environment**. |

---

## 2. Detailed Findings

### ✓ What is right

1.  **Use of Named Volumes:**
    *   `docker-compose.yml` explicitly defines named volumes for each stateful service. This is a best practice compared to `bind` mounts for data, as volumes are managed by the Docker engine and are more portable and easier to handle.

2.  **Well-Defined Backup Template:**
    *   The `backups/duplicati-job-template.json` file defines a solid backup job:
        *   **Clear Sources:** Correctly identifies key directories to backup (`./shared`, `./data`, `./models`).
        *   **Encryption Enabled:** Specifies `encryption-module: aes`, which is crucial for backup security.
        *   **Daily Schedule:** The `Schedule: "@daily"` is a reasonable starting point for most use cases.

### ✗ Problems Found

| ID | Severity | Problem | Impact |
| :- | :--- | :--- | :--- |
| **V-01** | **HIGH** | **Manual Backup Process** | There is no automation to configure Duplicati. An administrator must: 1) Start the stack. 2) Access the Duplicati UI. 3) Create a new backup job. 4) Configure the destination. 5) Configure the encryption passphrase. 6) Select source directories. This manual process is error-prone and easily forgotten. |
| **V-02** | **HIGH** | **Absence of Disaster Recovery Plan** | If the host server fails catastrophically, there is no step-by-step guide describing how to restore services and data on a new host. This significantly increases Recovery Time Objective (RTO) and data loss risk if restoration is performed incorrectly. |
| **V-03** | **MEDIUM** | **Potential Volume Permission Issues** | The fact that `sudo` is needed to inspect volume sizes in the diagnostic script is a "code smell". It indicates that UIDs/GIDs of processes inside containers might not match file ownership on the host, a common cause of "permission denied" errors in production. |

---

### ⚠️ Warnings/Recommendations

1.  **Database Backup:**
    *   The current backup relies on copying database volume files (`postgres_storage`). This is known as a "cold" or filesystem backup. To ensure data consistency, the best practice is to use database-specific tools like `pg_dump`. The current backup could capture the database in an inconsistent state if it is being written to during the process.

2.  **Restoration Testing:**
    *   A backup plan is not complete until the restoration process has been tested. There is no evidence that restoration tests have been performed.

---

### 🔧 Suggested Solutions

1.  **For V-01 (Automate Duplicati Configuration):**
    *   **Solution:** Create an initialization script for Duplicati.
        1.  **Create a Script (`scripts/init_duplicati.sh`):** This script would use the Duplicati API or its CLI (`duplicati-cli`) to automatically configure the backup job on first start.
        2.  **Script Logic:**
            *   Wait for Duplicati API availability.
            *   Read environment variables (e.g., `DUPLICATI_DESTINATION`, `DUPLICATI_PASSPHRASE`) from the `.env` file.
            *   Use `sed` or a similar tool to replace placeholders in `duplicati-job-template.json`.
            *   `POST` the resulting JSON to the Duplicati API endpoint to create/update the job.
        3.  **Run the Script:** Run this script as a `docker-compose` service that runs once at startup, or as part of the `start.sh` script.

2.  **For V-02 (Create a Recovery Plan):**
    *   **Solution:** Create a `DISASTER_RECOVERY.md` document.
        *   **Document Content:**
            *   **Prerequisites:** (e.g., new host with Docker installed).
            *   **Step 1: Restore Backups:** Detailed instructions on how to use the Duplicati UI or CLI to restore data from destination storage to a temporary directory.
            *   **Step 2: Re-initialize the Stack:** How to clone the repository, run `init_env.sh` and `setup-permissions.sh`.
            *   **Step 3: Import Restored Data:** `docker cp` or volume mount commands to move restored data to new Docker volumes.
            *   **Step 4: Verification:** How to verify that services have started correctly and data is intact.
        *   **Testing:** This procedure must be tested at least once to ensure it works as expected.

3.  **For V-03 (Fix Permissions):**
    *   **Solution:** Expand and enforce the use of `setup-permissions.sh`.
        *   Ensure that the `setup-permissions.sh` script creates host directories for **all** volumes that need it, not just logs.
        *   Use `PUID` and `PGID` variables from the `.env` file consistently across all `docker-compose.yml` services and in the `setup-permissions.sh` script so that permissions match.
