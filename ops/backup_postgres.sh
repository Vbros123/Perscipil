#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/privatelens_${STAMP}.dump"

pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl --file="$OUT"
sha256sum "$OUT" > "$OUT.sha256"

if [[ -n "${BACKUP_S3_URI:-}" ]]; then
  aws s3 cp "$OUT" "$BACKUP_S3_URI/"
  aws s3 cp "$OUT.sha256" "$BACKUP_S3_URI/"
fi

echo "$OUT"
