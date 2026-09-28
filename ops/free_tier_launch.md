> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

# Perspicil Free-Tier Launch

This is the exact remaining operator checklist. The application code and deployment manifests are already configured for this stack.

## Accounts

1. Create a Neon Free project and copy its pooled Postgres connection string.
2. Create a Resend Free account, verify one sending domain, and create an API key.
3. Optionally create a Sentry Developer project and copy its Python DSN.

## Render Secrets

Set these on the `privatelens` or `privatelens-api` web service:

```text
DATABASE_URL=<Neon pooled connection string>
JWT_SECRET=<openssl rand -hex 48>
METRICS_TOKEN=<openssl rand -hex 32>
RESEND_API_KEY=<Resend API key>
SMTP_FROM_EMAIL=<verified sender on your domain>
```

Set these non-secret values:

```text
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
ALLOWED_ORIGINS=https://privatelens.vercel.app
ALLOWED_HOSTS=privatelens.onrender.com,privatelens-api.onrender.com
APP_PUBLIC_URL=https://privatelens.vercel.app
EMAIL_DELIVERY_MODE=resend
DATA_MODE=public
AUTH_TOKEN_RETURN_IN_RESPONSE=false
```

Add `SENTRY_DSN` if a free Sentry project was created. Deploy the latest `main` commit after saving the variables.

## Vercel

The existing `privatelens` project is connected to GitHub and already deploys `frontend` from `main`. Confirm its production variable remains:

```text
VITE_API_URL=https://privatelens.onrender.com
```

## Backups

In GitHub, add Actions secrets:

```text
PRODUCTION_DATABASE_URL=<same Neon connection string>
BACKUP_ENCRYPTION_KEY=<openssl rand -hex 48>
```

Run `Encrypted Postgres backup` once from the Actions tab and download the encrypted artifact to confirm it exists.

## Acceptance Test

1. `GET https://privatelens.onrender.com/api/health` returns `status=ok`, `database=postgres`, `email=resend`, and `data_mode=public`.
2. Create an account from `https://privatelens.vercel.app/signup` and receive the verification email.
3. Log out and log back in.
4. Test forgot-password and complete a reset from the email link.
5. Add a company to the watchlist, open a report, compare companies, and delete a history item.
6. Confirm `/api/metrics` returns 404 without a token and metrics with `Authorization: Bearer <METRICS_TOKEN>`.

## Honest Limit

This free stack is suitable for an early customer pilot, not a bank-grade production claim. Render Free sleeps after inactivity, Neon Free has limited storage and restore history, and external legal and security reviews still require qualified humans.
