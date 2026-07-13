#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_RESTORE:-}" != "I_UNDERSTAND_THIS_OVERWRITES_DATA" ]]; then
  echo "Set CONFIRM_RESTORE=I_UNDERSTAND_THIS_OVERWRITES_DATA to continue" >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" || -z "${BACKUP_FILE:-}" ]]; then
  echo "DATABASE_URL and BACKUP_FILE are required" >&2
  exit 1
fi

if [[ -f "$BACKUP_FILE.sha256" ]]; then
  sha256sum --check "$BACKUP_FILE.sha256"
fi

pg_restore --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL" "$BACKUP_FILE"
