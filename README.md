# PrivateLens v2

> **Bloomberg for Private Companies** — PrivateScore™ financial health scoring for any US private company

Live: [privatelens.vercel.app](https://privatelens.vercel.app) · API: [privatelens.onrender.com](https://privatelens.onrender.com/docs)

---

## What It Does

Type in any US private company. Get a **PrivateScore™ (0–1000)** in seconds — synthesized from 14 alternative data signals across financial health, legal risk, operational signals, market sentiment, and digital presence.

**5 live data sources** (real-time, no API key needed):
- SEC EDGAR — regulatory filings
- Wikipedia API — brand legitimacy & age
- DuckDuckGo + HackerNews — news & media sentiment
- Indeed — job posting velocity
- USASpending.gov — federal contracts

**9 simulated signals** (clearly labeled, unlock with funding):
- UCC Filings · Court Records · Open Banking Flows · B2B Payment Behavior
- Employee Reviews · Insider Sentiment · Web Traffic · Social Media · Supply Chain

---

## Running Locally

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend (Vite + React)
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
# App: http://localhost:3001
```

---

## Architecture

```
privatelens/
├── backend/
│   ├── main.py                  # FastAPI app, middleware, error handling
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── cache.py             # TTL in-memory LRU cache
│   │   └── limiter.py           # Sliding window rate limiter
│   ├── routers/
│   │   └── score.py             # /api/score, /api/compare, /api/history
│   ├── services/
│   │   ├── collectors.py        # 14 signal collectors (5 real, 9 simulated)
│   │   ├── scorer.py            # PrivateScore™ weighted algorithm + risk flags
│   │   └── history.py           # Search history store
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx              # Full dashboard: search, gauge, signals, compare
    │   ├── styles/
    │   │   ├── global.css       # Dark theme design system
    │   │   └── App.css          # Component styles
    │   └── main.jsx
    ├── index.html
    └── vite.config.js
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/score?company=NAME` | Get PrivateScore™ for any company |
| `GET /api/compare?companies=A,B,C` | Compare up to 4 companies |
| `GET /api/history` | Recent search history |
| `GET /api/signals` | All 14 signals with data source status |
| `GET /api/health` | Health check |
| `GET /docs` | Swagger UI |

---

## Signal Weights (PrivateScore™ Model)

| Signal | Weight | Status |
|---|---|---|
| Open Banking Payment Flows | 13% | Simulated → Section 1033 API |
| B2B Payment Behavior | 12% | Simulated → D&B Paydex |
| Job Posting Velocity | 11% | **Live** (Indeed) |
| UCC Filings & Lien Activity | 10% | Simulated → State UCC APIs |
| Court Records & Litigation | 9% | Simulated → PACER |
| News & Media Sentiment | 8% | **Live** (DuckDuckGo + HN) |
| Employee & Customer Reviews | 7% | Simulated → Glassdoor |
| Insider & Employee Sentiment | 6% | Simulated → Glassdoor |
| Web Traffic Trends | 6% | Simulated → SimilarWeb |
| Brand Legitimacy & Web Presence | 5% | **Live** (Wikipedia) |
| SEC / Regulatory Filings | 5% | **Live** (EDGAR) |
| Social Media Activity | 4% | Simulated → Twitter API |
| Supply Chain & Vendor Signals | 3% | Simulated → RiskMethods |
| Government Contract Awards | 1% | **Live** (USASpending.gov) |


Built by **Vijith Velamuri** · Sophomore · Cary, NC  
[privatelens.vercel.app](https://privatelens.vercel.app) · vijithvelamuri@gmail.com
