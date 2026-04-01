#!/usr/bin/env bash
# LicitaBrasil — Database Backup Script
# Usage: ./scripts/backup.sh
# Env vars: PGUSER, PGDATABASE, PGHOST (defaults below)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_USER="${PGUSER:-licitabrasil}"
DB_NAME="${PGDATABASE:-licitabrasil}"
DB_HOST="${PGHOST:-localhost}"
KEEP_DAYS="${KEEP_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="${BACKUP_DIR}/licitabrasil_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] Starting backup of ${DB_NAME} at $(date)"

pg_dump -U "$DB_USER" -h "$DB_HOST" "$DB_NAME" | gzip > "$FILENAME"

SIZE=$(du -h "$FILENAME" | cut -f1)
echo "[backup] Created ${FILENAME} (${SIZE})"

# Remove backups older than KEEP_DAYS
DELETED=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$KEEP_DAYS" -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
  echo "[backup] Cleaned up ${DELETED} old backup(s)"
fi

echo "[backup] Done at $(date)"
