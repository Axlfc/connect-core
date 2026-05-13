#!/usr/bin/env bash
set -euo pipefail

# Orquesta backups de: PostgreSQL (dump), Qdrant (volumen), y volúmenes críticos
# Uso básico: ./scripts/backup.sh

BACKUP_DIR=${BACKUP_DIR:-backups}
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
DIR="$BACKUP_DIR/$TIMESTAMP"

POSTGRES_SERVICE=${POSTGRES_SERVICE:-postgres}
POSTGRES_DB=${POSTGRES_DB:-${POSTGRES_DB:-}}
POSTGRES_USER_FILE=${POSTGRES_USER_FILE:-/run/secrets/postgres_user}
POSTGRES_PASS_FILE=${POSTGRES_PASS_FILE:-/run/secrets/postgres_password}

COMPOSE_CMD=""
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "Error: docker compose or docker-compose not found." >&2
  exit 1
fi

VOLumes_DEFAULT=(postgres_storage n8n_storage qdrant_storage duplicati_config comfyui_local)
VOLUMES=(${VOLUMES:-${VOLumes_DEFAULT[*]}})

DRY_RUN=0
KEEP_DAYS=${KEEP_DAYS:-14}

usage(){
  cat <<EOF
Usage: $0 [--dry-run] [--keep-days N]
  --dry-run   : show actions without executing
  --keep-days : remove backups older than N days (default: ${KEEP_DAYS})
EOF
}

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --keep-days) KEEP_DAYS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

run(){
  echo "+ $*"
  if [[ $DRY_RUN -eq 0 ]]; then
    eval "$@"
  fi
}

mkdir -p "$DIR"
echo "Backup directory: $DIR"

# 1) PostgreSQL dump (pg_dumpall)
echo "-> Dumping PostgreSQL from service '$POSTGRES_SERVICE'"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: $COMPOSE_CMD exec -T $POSTGRES_SERVICE pg_dumpall -U <user> > $DIR/postgres.sql"
else
  # Use secret files inside container if present
  $COMPOSE_CMD exec -T "$POSTGRES_SERVICE" sh -lc \
    "PGPASSWORD=\$(cat ${POSTGRES_PASS_FILE} 2>/dev/null || echo) pg_dumpall -U \$(cat ${POSTGRES_USER_FILE} 2>/dev/null || echo)" \
    > "$DIR/postgres.sql" || echo "Warning: pg_dumpall returned non-zero exit code"
fi

# 2) Qdrant: snapshot by exporting the data volume
echo "-> Exporting Qdrant volume (qdrant_storage)"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: docker run --rm -v qdrant_storage:/from alpine sh -c 'tar -C /from -czf - .' > $DIR/qdrant_storage.tar.gz"
else
  docker run --rm -v qdrant_storage:/from alpine sh -c "tar -C /from -czf - ." > "$DIR/qdrant_storage.tar.gz"
fi

# 3) Tar other critical volumes
for vol in "${VOLUMES[@]}"; do
  out="$DIR/${vol}.tar.gz"
  echo "-> Exporting volume: $vol -> $out"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: docker run --rm -v ${vol}:/from alpine sh -c 'tar -C /from -czf - .' > $out"
  else
    docker run --rm -v "${vol}:/from" alpine sh -c "tar -C /from -czf - ." > "$out" || echo "Warning: failed to export volume $vol"
  fi
done

# 4) Metadata manifest
cat > "$DIR/manifest.json" <<JSON
{
  "timestamp": "$TIMESTAMP",
  "postgres_service": "$POSTGRES_SERVICE",
  "volumes": "${VOLUMES[*]}",
  "compose_cmd": "$COMPOSE_CMD"
}
JSON

echo "Backup completed: $DIR"

# 5) Prune old backups
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: find $BACKUP_DIR -maxdepth 1 -mtime +$KEEP_DAYS -type d -print"
else
  if [[ -d "$BACKUP_DIR" ]]; then
    find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -print -exec rm -rf {} + || true
  fi
fi

echo "Done."
