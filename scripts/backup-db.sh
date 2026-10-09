#!/bin/bash
# Daily pg_dump of the RDS database (extra to RDS automated snapshots)
# crontab: 0 2 * * * /opt/apps/rag-support-assistant-backend/scripts/backup-db.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"
PG_IMAGE="${PG_IMAGE:-postgres:17-alpine}"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
docker run --rm --env-file "$APP_DIR/.env" "$PG_IMAGE" sh -c \
  'PGPASSWORD="$DB_PASSWORD" PGSSLMODE="${DB_SSLMODE:-require}" pg_dump -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME"' \
  | gzip > "$BACKUP_DIR/supportai_${DATE}.sql.gz"
find "$BACKUP_DIR" -name "supportai_*.sql.gz" -mtime +7 -delete
echo "Backup OK: $BACKUP_DIR/supportai_${DATE}.sql.gz"
