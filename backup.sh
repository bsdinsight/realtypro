#!/usr/bin/env bash
# Realty Project — back up the `dev` database + filestore.
#
# Run from the stack directory (where docker-compose.yml lives) on the
# host where the realtypro stack is up.
#
# Usage:
#   ./backup.sh                        # writes to ./backups/
#   ./backup.sh /mnt/nfs               # writes to /mnt/nfs/
#   DB_NAME=foo ./backup.sh            # back up a non-default DB
#
# Output:
#   <out>/realtypro-YYYY-MM-DD_HHMM/
#     ├─ dev.dump.gz       (pg_dump -Fc, gzipped)
#     ├─ filestore.tar.gz  (data/filestore/<dbname>/ archived)
#     └─ MANIFEST.txt
#
# Restore with `pg_restore` (see DEPLOY.md, "Restore from backup").

set -euo pipefail

DB_NAME="${DB_NAME:-dev}"
PG_USER="${POSTGRES_USER:-odoo}"
OUT_BASE="${1:-./backups}"
TS="$(date +%Y-%m-%d_%H%M)"
OUT="$OUT_BASE/realtypro-$TS"

cd "$(dirname "$0")"
mkdir -p "$OUT"

echo "==> Backing up DB '$DB_NAME' to $OUT"

# -- Postgres dump (custom format = compressed, parallelizable restore)
echo "  - pg_dump $DB_NAME"
docker compose exec -T db pg_dump -U "$PG_USER" -Fc "$DB_NAME" \
  | gzip > "$OUT/$DB_NAME.dump.gz"

# -- Filestore
# data/filestore/<dbname>/ holds attachments. Skip silently if missing
# (a freshly-initialized DB has none yet).
if [ -d "./data/filestore/$DB_NAME" ]; then
  echo "  - tar filestore for $DB_NAME"
  tar -czf "$OUT/filestore.tar.gz" -C ./data/filestore "$DB_NAME"
else
  echo "  - (no filestore at ./data/filestore/$DB_NAME, skipping)"
fi

# -- Manifest
{
  echo "Realty Project backup"
  echo "Database: $DB_NAME"
  echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Stack dir: $(pwd)"
  echo ""
  echo "Files:"
  for f in "$OUT"/*; do
    [ -f "$f" ] || continue
    SIZE=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f")
    echo "  - $(basename "$f") (${SIZE} bytes)"
  done
} > "$OUT/MANIFEST.txt"

echo "==> Backup complete: $OUT"
ls -lh "$OUT"
