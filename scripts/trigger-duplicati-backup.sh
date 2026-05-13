#!/usr/bin/env bash
set -euo pipefail

# trigger-duplicati-backup.sh
# Lee backups/job.id y lanza ejecución del job en Duplicati (best-effort)

JOB_ID_FILE=backups/job.id

if [[ ! -f "$JOB_ID_FILE" ]]; then
  echo "Job id file not found: $JOB_ID_FILE" >&2
  exit 2
fi

JOB_ID=$(cat "$JOB_ID_FILE" | tr -d '[:space:]')
if [[ -z "$JOB_ID" ]]; then
  echo "Empty job id in $JOB_ID_FILE" >&2
  exit 2
fi

echo "Triggering Duplicati job: $JOB_ID"

try(){
  local url="$1"
  if curl -fsS -X POST "$url" -o /dev/null; then
    echo "Triggered via $url"
    return 0
  else
    echo "Attempt $url failed"
    return 1
  fi
}

ENDPOINTS=(
  "http://localhost:8200/api/backup/run?jobid=$JOB_ID"
  "http://localhost:8200/api/backup/$JOB_ID/run"
  "http://localhost:8200/api/backup/run/$JOB_ID"
  "http://localhost:8200/api/backup/run"
)

for e in "${ENDPOINTS[@]}"; do
  if try "$e"; then
    exit 0
  fi
done

echo "All trigger attempts failed. Visit http://localhost:8200 and run job manually." >&2
exit 3
