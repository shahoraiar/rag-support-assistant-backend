#!/bin/bash
# Daily Postgres backup on Oracle VPS
# crontab: 0 2 * * * /opt/apps/rag-support-assistant-backend/scripts/backup-db.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"
CONTAINER="${DB_CONTAINER:-supportai_db}"
DB_NAME="${DB_NAME:-supportai}"
DB_USER="${DB_USER:-postgres}"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/supportai_${DATE}.sql.gz"
find "$BACKUP_DIR" -name "supportai_*.sql.gz" -mtime +7 -delete
echo "Backup OK: $BACKUP_DIR/supportai_${DATE}.sql.gz"
