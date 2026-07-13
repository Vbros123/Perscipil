# PrivateLens

PrivateLens is a full-stack private-company financial health research workspace. It combines a FastAPI scoring API with an authenticated React dashboard for company reports, peer comparison, watchlists, search history, account settings, pricing, and developer documentation.

Live frontend: https://privatelens.vercel.app

Backend docs: https://privatelens.onrender.com/docs

PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.

## Product Surface

- Account signup, login, JWT sessions, and `/api/auth/me`
- PrivateScore company reports with live/modelled signal labels
- User-specific history and saved company watchlists
- Peer comparison for two to four companies
- Workspace settings, account profile, pricing, and developer pages
- SQLite by default, with `DATABASE_URL` support for Postgres-style deployments

## Repository Structure

```text
backend/
  main.py
  core/
    config.py
    database.py
    limiter.py
    cache.py
    security.py
  models/
    user.py
    company.py
    settings.py
  routers/
    auth.py
    score.py
    compare.py
    history.py
    watchlist.py
    settings.py
    users.py
  schemas/
    auth.py
    company.py
    settings.py
  services/
    collectors.py
    scorer.py
    history.py
    reports.py

frontend/
  src/
    api/
    components/
    context/
    pages/
    styles/
```

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend API docs run at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Vite runs on `http://localhost:3001`.

## Environment Variables

### Backend

| Name | Required | Default | Notes |
|---|---:|---|---|
| `DATABASE_URL` | No | `sqlite:///./privatelens.db` | Use Postgres or a Render persistent disk in production. |
| `JWT_SECRET` | Yes in production | `change-this-in-production` | Set a long random secret. |
| `JWT_EXPIRES_MINUTES` | No | `10080` | Default is seven days. |
| `ALLOWED_ORIGINS` | No | `*` | Comma-separated origins, for example `https://privatelens.vercel.app`. |
| `FRONTEND_URL` | No | `http://localhost:5173` | Added to CORS when `ALLOWED_ORIGINS` is not `*`. |
| `HTTP_TIMEOUT` | No | `8.0` | External collector timeout. |
| `RATE_LIMIT_PER_MINUTE` | No | `30` | Per-IP score/compare rate limit. |

### Frontend

| Name | Required | Example |
|---|---:|---|
| `VITE_API_URL` | Yes in production | `https://privatelens.onrender.com` |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/signup` | Create account and return bearer token |
| `POST` | `/api/auth/login` | Log in and return bearer token |
| `GET` | `/api/auth/me` | Current authenticated user |
| `PATCH` | `/api/users/me` | Update profile |
| `GET` | `/api/score?company=NAME` | Score a company and return a report |
| `GET` | `/api/compare?companies=A,B` | Compare two to four companies |
| `GET` | `/api/watchlist` | List saved companies |
| `POST` | `/api/watchlist` | Save or update a company |
| `PATCH` | `/api/watchlist/{id}` | Update saved notes/tags |
| `DELETE` | `/api/watchlist/{id}` | Remove saved company |
| `GET` | `/api/history` | Authenticated search history |
| `DELETE` | `/api/history` | Clear history |
| `DELETE` | `/api/history/{id}` | Delete one history row |
| `GET` | `/api/settings` | Get workspace settings |
| `PATCH` | `/api/settings` | Update workspace settings |
| `GET` | `/api/signals` | Signal library |
| `GET` | `/api/health` | Health check |

Authenticated endpoints use:

```bash
Authorization: Bearer <token>
```

## Deployment

### Render Backend

1. Build command: `pip install -r requirements.txt`
2. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Root directory: `backend`
4. Set `JWT_SECRET` to a strong production value.
5. Set `ALLOWED_ORIGINS=https://privatelens.vercel.app`.
6. Set `DATABASE_URL` to a managed Postgres URL or attach a persistent disk if using SQLite.

SQLite works locally and for demos. Render free instances have ephemeral filesystems unless a disk is attached, so production user data should use Postgres.

### Vercel Frontend

1. Root directory: `frontend`
2. Build command: `npm run build`
3. Output directory: `dist`
4. Environment variable: `VITE_API_URL=https://privatelens.onrender.com`
5. `frontend/vercel.json` rewrites all app routes to `index.html` for React Router.

## Data Sources And Limits

Live/free collectors currently include SEC EDGAR, Wikipedia, DuckDuckGo, HackerNews, and USASpending.gov. Some external pages such as job boards may block automated requests, in which case PrivateLens falls back to deterministic modelled signals.

Simulated data is clearly marked with `is_simulated: true` in API responses and shown as modelled in the UI. These signals are placeholders for licensed data feeds such as UCC filings, court records, open banking cash-flow data, B2B payment behavior, review data, web traffic, social activity, and supply-chain risk.

## Validation

Frontend:

```bash
cd frontend
npm run build
```

Backend smoke testing can be done with FastAPI `TestClient` or by running the server locally and calling signup, login, settings, watchlist, score, history, and compare endpoints.
