#!/usr/bin/env bash
set -euo pipefail

# Orquesta un backup y lo coloca en la carpeta que Duplicati tiene montada.
# Luego intenta pedir a Duplicati que ejecute un backup inmediatamente.
# Uso: ./scripts/backup-to-duplicati.sh [--no-trigger] [--dry-run]

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

DRY_RUN=0
TRIGGER=1

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --no-trigger) TRIGGER=0; shift ;;
    -h|--help) echo "Usage: $0 [--no-trigger] [--dry-run]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

BACKUP_SOURCES_DIR="$ROOT_DIR/backups/sources"

mkdir -p "$BACKUP_SOURCES_DIR"

echo "Preparing backup in: $BACKUP_SOURCES_DIR"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: would run: BACKUP_DIR=$BACKUP_SOURCES_DIR $SCRIPT_DIR/backup.sh"
  exit 0
fi

# Run the generic backup script, storing output under backups/sources/<timestamp>
BACKUP_DIR=$BACKUP_SOURCES_DIR "$SCRIPT_DIR/backup.sh"

echo "Backup files created under $BACKUP_SOURCES_DIR"

if [[ $TRIGGER -eq 0 ]]; then
  echo "Triggering disabled (--no-trigger). Exiting."; exit 0
fi

# Try to notify Duplicati to run a backup. It's best-effort: several endpoints tried.
echo "Attempting to trigger Duplicati to run backups (best-effort)..."

try_endpoint(){
  local url="$1"
  if curl -sfS -X POST "$url" -o /dev/null; then
    echo "Triggered via $url"
    return 0
  fi
  return 1
}

ENDPOINTS=(
  "http://localhost:8200/api/backup"
  "http://localhost:8200/api/backup/backupnow"
  "http://localhost:8200/api/backup/run"
  "http://localhost:8200/rpc/backup"
)

success=0
for e in "${ENDPOINTS[@]}"; do
  if try_endpoint "$e"; then
    success=1
    break
  fi
done

if [[ $success -eq 0 ]]; then
  echo "Could not trigger Duplicati automatically."
  echo "Check Duplicati UI at http://localhost:8200 and create a job that includes /source (mounted) or trigger existing job manually."
else
  echo "Duplicati triggered successfully (or accepted request)."
fi

echo "Done."
