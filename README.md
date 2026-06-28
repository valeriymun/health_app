# Health Dashboard

Personal health data dashboard aggregating data from **Apple Health**, **Oura Ring**, **Garmin Connect**, and **Hevy**.

## Features

- **Unified Dashboard** — View trends for heart rate, HRV, sleep, steps, workouts across all sources
- **Apple Health** — Import via XML export upload or auto-sync via Apple Shortcuts
- **Oura Ring** — API integration with full history sync
- **Garmin Connect** — Full history sync including activities, sleep, and body metrics. Uses cached `garth` tokens at `~/.garminconnect` if present (skips re-entering password / MFA), falls back to email + password.
- **Hevy** — Strength workouts with set-level detail (weights, reps, RPE) via the Hevy API v1 (`/api/ingest/hevy/sync`, `/api/ingest/hevy/status`)
- **Health Reports** — Download Markdown reports to use with Claude as your AI health advisor

## Quick Start

### 1. Configure credentials

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Oura token, Garmin credentials, etc.
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

### 3. Or run locally

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 4. Open the dashboard

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Data Sources Setup

### Apple Health
- **Option A (XML Upload):** On iPhone go to Health app → Profile → Export All Health Data. Upload the ZIP at Settings page.
- **Option B (Shortcuts Auto-Sync):** Create an Apple Shortcut that posts health data to `/api/ingest/apple-health/shortcuts` with your API key.

### Oura Ring
1. Get a Personal Access Token from https://cloud.ouraring.com/personal-access-tokens
2. Set `OURA_PERSONAL_ACCESS_TOKEN` in `.env`
3. Click "Sync" on the Settings page

### Garmin Connect
1. Set `GARMIN_EMAIL` and `GARMIN_PASSWORD` in `.env`
2. Click "Sync" on the Settings page

## Using as AI Health Advisor

1. Click the **Report** button on the dashboard (or go to Settings → Health Reports)
2. Download a Markdown report for your desired time period
3. Upload the report to Claude and ask for health insights, trends analysis, or recommendations

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/overview` | GET | Dashboard overview data |
| `/api/dashboard/trends/{metric}` | GET | Trend data for a metric |
| `/api/dashboard/sleep/trends` | GET | Sleep trend data |
| `/api/dashboard/workouts/summary` | GET | Workout summary |
| `/api/reports/health-summary` | GET | Generate health report |
| `/api/ingest/apple-health/upload` | POST | Upload Apple Health XML |
| `/api/ingest/apple-health/shortcuts` | POST | Apple Shortcuts webhook |
| `/api/ingest/oura/sync` | POST | Sync Oura data |
| `/api/ingest/garmin/sync` | POST | Sync Garmin data |
| `/api/ingest/hevy/sync` | POST | Sync Hevy strength workouts (sets + reps + weight) |
| `/api/ingest/hevy/status` | GET  | Verify Hevy API key and return remote workout count |
