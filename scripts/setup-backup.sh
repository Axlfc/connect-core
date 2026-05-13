#!/usr/bin/env bash
set -euo pipefail

# setup-backup.sh
# Script interactivo para configurar la integración con Duplicati.
# Crea backups/duplicati-job.json rellenando plantilla y ofrece crear el job via API.

mkdir -p backups
TEMPLATE=backups/duplicati-job-template.json
OUT=backups/duplicati-job.json

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Template missing: $TEMPLATE" >&2
  exit 2
fi

echo "Configuring Duplicati job for cognito-stack"
read -p "Destination URI (e.g. s3://bucket/path or webdav://...): " DEST
read -p "Encryption passphrase (leave empty for no encryption): " -s PASSPHRASE
echo
read -p "Retention policy (e.g. keep-last 30): " RETENTION

cp "$TEMPLATE" "$OUT"
sed -i "s|<DESTINATION_URI>|$DEST|g" "$OUT"
sed -i "s|<ENCRYPTION_PASSPHRASE>|$PASSPHRASE|g" "$OUT"
sed -i "s|<RETENTION_POLICY>|$RETENTION|g" "$OUT"

echo "Created $OUT. You can review and edit it before creating the job."
echo "To create and register the job in Duplicati, run: ./scripts/create-duplicati-job.sh"
