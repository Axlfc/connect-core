#!/usr/bin/env bash
set -euo pipefail

# create-duplicati-job.sh
# Crea un job en Duplicati a partir de backups/duplicati-job-template.json
# Guarda jobId en ./backups/job.id

TEMPLATE=backups/duplicati-job-template.json
OUT=backups/duplicati-job.json
JOB_ID_FILE=backups/job.id

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Template not found: $TEMPLATE" >&2
  exit 2
fi

echo "Reading template $TEMPLATE"
cp "$TEMPLATE" "$OUT"

echo "Please edit $OUT if you want to customize before creating the job."
read -p "Create job now from $OUT? [y/N] " yn
case "$yn" in
  [Yy]*) ;;
  *) echo "Aborted by user."; exit 0 ;;
esac

echo "Waiting for Duplicati API to be available at http://localhost:8200..."
for i in {1..30}; do
  if curl -fsS http://localhost:8200 >/dev/null 2>&1; then
    echo "Duplicati is reachable"; break
  fi
  sleep 2
done

if ! curl -fsS http://localhost:8200 >/dev/null 2>&1; then
  echo "Duplicati not reachable after wait. Aborting." >&2
  exit 3
fi

# Try to POST job JSON to candidate endpoints (best-effort). If API differs, instruct manual import.
PAYLOAD=$(cat "$OUT")
set +e
echo "Attempting to create job via API (best-effort)..."
RESP=$(curl -sfS -X POST "http://localhost:8200/api/backup/job" -H "Content-Type: application/json" -d "$PAYLOAD" 2>/dev/null)
RC=$?
set -e

if [[ $RC -ne 0 || -z "$RESP" ]]; then
  echo "API call didn't return a job id. Saving job JSON to $OUT and asking user to import via UI." 
  echo "If you want, open http://localhost:8200 -> Add backup -> Import and paste the JSON from $OUT."
  exit 0
fi

# Try to extract jobId from response
JOB_ID=$(echo "$RESP" | sed -n 's/.*"jobId"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p')
if [[ -z "$JOB_ID" ]]; then
  # fallback: response might be the job id directly
  JOB_ID=$(echo "$RESP" | tr -d '"[:space:]')
fi

if [[ -n "$JOB_ID" ]]; then
  mkdir -p backups
  echo "$JOB_ID" > "$JOB_ID_FILE"
  echo "Job created, id saved to $JOB_ID_FILE: $JOB_ID"
else
  echo "Could not parse job id from API response. Response was:" >&2
  echo "$RESP" >&2
  echo "Please import $OUT via the Duplicati UI." >&2
fi
