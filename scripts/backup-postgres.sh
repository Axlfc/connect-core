#!/bin/bash
set -euo pipefail

# ========================================
# PostgreSQL Backup Script
# ========================================
#
# Description:
# This script performs a backup of a PostgreSQL database from a running Docker container.
# It is designed to be executed by a cron job or a similar scheduling mechanism on the host machine.
#
# Pre-requisites:
# 1. An environment file (`.env`) must be present in the script's execution directory
#    (or loaded beforehand) containing the following variables:
#    - POSTGRES_USER: The username for the PostgreSQL database.
#    - POSTGRES_DB: The name of the database to be backed up.
#
# 2. The `docker` command must be available and executable by the user running the script.
#
# Usage:
# ./scripts/backup-postgres.sh
#
# The script will create a timestamped SQL dump in the './backups/sources/sql/' directory.
# Ensure this directory exists and has the correct permissions.
# ========================================

# Directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Project root directory (assuming the script is in ./scripts)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# Destination directory for the SQL dump
BACKUP_DIR="${PROJECT_ROOT}/backups/sources/sql"

# Load environment variables from the .env file in the project root
if [ -f "${PROJECT_ROOT}/.env" ]; then
    export $(cat "${PROJECT_ROOT}/.env" | grep -v '#' | sed 's/\r$//' | awk '/=/ {print $1}')
fi

# Check for required environment variables
if [ -z "${POSTGRES_USER}" ] || [ -z "${POSTGRES_DB}" ]; then
    echo "Error: POSTGRES_USER and POSTGRES_DB environment variables are required."
    echo "Please ensure they are defined in the .env file in the project root."
    exit 1
fi

# Ensure the backup directory exists
mkdir -p "${BACKUP_DIR}"

# Generate a timestamped filename for the backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/postgres-${TIMESTAMP}.sql"

echo "Starting PostgreSQL backup..."
echo "Database: ${POSTGRES_DB}"
echo "User: ${POSTGRES_USER}"
echo "Destination: ${BACKUP_FILE}"

# Execute pg_dump inside the 'postgres' container
# The output is redirected to the backup file on the host machine
docker exec postgres pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" > "${BACKUP_FILE}"

# Check the exit code of the pg_dump command
if [ $? -eq 0 ]; then
    echo "Backup completed successfully."
else
    echo "Error: Backup failed. Check Docker logs for the 'postgres' container for more details."
    # Optional: remove the failed backup file
    # rm "${BACKUP_FILE}"
    exit 1
fi

# Optional: Prune old backups (e.g., keep the last 7 days)
# find "${BACKUP_DIR}" -name "postgres-*.sql" -mtime +7 -exec rm {} \;
# echo "Old backups have been pruned."

echo "Script finished."
