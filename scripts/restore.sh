#!/usr/bin/env bash
set -euo pipefail

# Restauración de backups creados por scripts/backup.sh
# Uso principal: ./scripts/restore.sh --list
# Para restaurar: ./scripts/restore.sh <timestamp> [--restore-postgres] [--restore-volumes]

BACKUP_DIR=${BACKUP_DIR:-backups}
COMPOSE_CMD=""
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "Error: docker compose or docker-compose not found." >&2
  exit 1
fi

usage(){
  cat <<EOF
Usage: $0 --list
       $0 <timestamp> [--restore-postgres] [--restore-volumes]
  --list            : lista backups disponibles
  --restore-postgres: importar SQL dump into postgres
  --restore-volumes : restore tarballs into their docker volumes (stops affected services)
EOF
}

if [[ ${#} -eq 0 ]]; then
  usage; exit 1
fi

if [[ "$1" == "--list" ]]; then
  if [[ -d "$BACKUP_DIR" ]]; then
    ls -1 "$BACKUP_DIR"
  else
    echo "No backup dir: $BACKUP_DIR"
  fi
  exit 0
fi

TIMESTAMP="$1"; shift || true
DIR="$BACKUP_DIR/$TIMESTAMP"
if [[ ! -d "$DIR" ]]; then
  echo "Backup not found: $DIR" >&2
  exit 2
fi

RESTORE_POSTGRES=0
RESTORE_VOLUMES=0
while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --restore-postgres) RESTORE_POSTGRES=1; shift ;;
    --restore-volumes) RESTORE_VOLUMES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ $RESTORE_POSTGRES -eq 1 ]]; then
  SQL_FILE="$DIR/postgres.sql"
  if [[ ! -f "$SQL_FILE" ]]; then
    echo "Postgres SQL dump not found: $SQL_FILE" >&2
  else
    echo "Restoring PostgreSQL from $SQL_FILE"
    # Pipe SQL into psql inside container, reading secrets inside container
    cat "$SQL_FILE" | $COMPOSE_CMD exec -T postgres sh -lc \
      "PGPASSWORD=\$(cat /run/secrets/postgres_password 2>/dev/null || echo) psql -U \$(cat /run/secrets/postgres_user 2>/dev/null || echo) -d \$(cat /run/secrets/postgres_db 2>/dev/null || echo || echo 'postgres')" \
      || echo "Warning: psql returned non-zero exit code"
  fi
fi

if [[ $RESTORE_VOLUMES -eq 1 ]]; then
  echo "Restoring volume tarballs from $DIR"
  # Stop services that may use volumes
  echo "Stopping postgres and qdrant to restore volumes..."
  $COMPOSE_CMD stop postgres qdrant || true

  for tarball in "$DIR"/*.tar.gz; do
    base=$(basename "$tarball")
    volname=${base%.tar.gz}
    echo "-> Restoring $tarball -> volume $volname"
    if [[ "$tarball" == *postgres_storage.tar.gz ]]; then
      echo "Note: restoring raw Postgres volume files may be unsafe; prefer SQL restore when possible."
    fi
    docker run --rm -i -v "$volname:/to" alpine sh -c "tar -C /to -xzf -" < "$tarball" || echo "Warning: failed to restore $volname"
  done

  echo "Starting services back..."
  $COMPOSE_CMD up -d postgres qdrant || true
fi

echo "Restore finished. Review logs and run health checks."
