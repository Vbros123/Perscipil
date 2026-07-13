# PrivateLens Backup Runbook

## Objective

Protect production customer data stored in managed Postgres and prove restore capability on a regular cadence.

## Required Production Setup

- Managed Postgres is configured through `DATABASE_URL`.
- Render automated database backups are enabled on the database service.
- A separate off-platform backup destination is configured, such as S3, with retention policies.
- `pg_dump`, `pg_restore`, and the destination CLI are available in the backup runner.

## Nightly Backup

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

## Retention

- Daily backups: 30 days.
- Weekly backups: 12 weeks.
- Monthly backups: 12 months.
- Security incidents or legal holds override deletion.
