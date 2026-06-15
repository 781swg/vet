#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/restore_postgres.sh ./backups/vet_ai_manager_YYYYmmdd_HHMMSS.dump"
  exit 1
fi

DB_NAME="${POSTGRES_DB:-vet_ai_manager}"
DB_USER="${POSTGRES_USER:-postgres}"
BACKUP_FILE="$1"

cat "$BACKUP_FILE" | docker compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists
echo "Restored: $BACKUP_FILE"

