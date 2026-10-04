> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

# Perspicil Backup Runbook

## Objective

Protect production customer data stored in managed Postgres and prove restore capability on a regular cadence.

## Required Production Setup

- Managed Postgres is configured through `DATABASE_URL`.
- Neon point-in-time restore is available for the provider's current free retention window.
- GitHub Actions secrets `PRODUCTION_DATABASE_URL` and `BACKUP_ENCRYPTION_KEY` are configured.
- `pg_dump`, `pg_restore`, and the destination CLI are available in the backup runner.

## Automated Free-Tier Backup

`.github/workflows/postgres-backup.yml` runs daily and on manual dispatch. It creates a custom-format Postgres dump, encrypts it with AES-256, and stores only the encrypted file as a private GitHub Actions artifact for seven days.

Generate the encryption key once and store it only in GitHub Actions secrets and your password manager:

```bash
openssl rand -hex 48
```

## Manual Backup

```bash
cd ops
DATABASE_URL="$PRODUCTION_DATABASE_URL" BACKUP_S3_URI="s3://your-private-bucket/privatelens" ./backup_postgres.sh
```

## Restore Drill

Run this against a non-production database monthly:

```bash
cd ops
DATABASE_URL="$STAGING_DATABASE_URL" \
BACKUP_FILE="./backups/privatelens_YYYYMMDDTHHMMSSZ.dump" \
CONFIRM_RESTORE=I_UNDERSTAND_THIS_OVERWRITES_DATA \
./restore_postgres.sh
```

## Acceptance Criteria

- Backup file exists and has a matching SHA-256 checksum.
- Restore completes into staging without errors.
- `/api/health` returns `status=ok`.
- Login, watchlist, history, and score report workflows are manually verified in staging.

## Free-Tier Retention

- Encrypted GitHub Actions artifacts: 7 days.
- Neon point-in-time restore: provider's current free-plan window.
- Longer retention and independent off-platform storage require a paid service or a separate operator-owned backup destination.
