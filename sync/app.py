#!/usr/bin/env python3
"""Flask app to sync Oura Ring + Garmin data to Google Sheets."""

import json
import os
import secrets
from datetime import date, timedelta

import gspread
import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, session, url_for
from garminconnect import Garmin
from google.oauth2.service_account import Credentials

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

# ── Config ─────────────────────────────────────────────────────────────────────
OURA_CLIENT_ID    = os.getenv("OURA_CLIENT_ID")
OURA_CLIENT_SECRET = os.getenv("OURA_CLIENT_SECRET")
OURA_REDIRECT_URI = "http://localhost:5000/callback"
OURA_TOKEN_FILE   = os.path.join(os.path.dirname(__file__), "oura_token.json")
GARMIN_HOME       = os.path.expanduser("~/.garth_health_sync")
GOOGLE_SHEET_ID   = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "service-account.json")


def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


# ── Oura ───────────────────────────────────────────────────────────────────────

def load_oura_token():
    if os.path.exists(OURA_TOKEN_FILE):
        with open(OURA_TOKEN_FILE) as f:
            return json.load(f)
    return None


def save_oura_token(t):
    with open(OURA_TOKEN_FILE, "w") as f:
        json.dump(t, f)


def oura_get(path, params=None):
    token = load_oura_token()
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    r = requests.get(
        f"https://api.ouraring.com/v2/usercollection/{path}",
        headers=headers, params=params,
    )
    if r.status_code == 401:
        r2 = requests.post("https://api.ouraring.com/oauth/token", data={
            "grant_type":    "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id":     OURA_CLIENT_ID,
            "client_secret": OURA_CLIENT_SECRET,
        })
        if r2.ok:
            token = r2.json()
            save_oura_token(token)
            headers = {"Authorization": f"Bearer {token['access_token']}"}
            r = requests.get(
                f"https://api.ouraring.com/v2/usercollection/{path}",
                headers=headers, params=params,
            )
    return r.json()


def fetch_oura_sleep(d):
    p = {"start_date": d, "end_date": d}
    sessions   = oura_get("sleep",       p).get("data", [])
    score_data = oura_get("daily_sleep", p).get("data", [])
    if not sessions:
        return {}
    s = max(sessions, key=lambda x: x.get("total_sleep_duration", 0))
    return {
        "score":      score_data[0].get("score") if score_data else None,
        "total_hrs":  round(s.get("total_sleep_duration", 0) / 3600, 2),
        "deep_min":   round(s.get("deep_sleep_duration",  0) / 60),
        "rem_min":    round(s.get("rem_sleep_duration",   0) / 60),
        "light_min":  round(s.get("light_sleep_duration", 0) / 60),
        "efficiency": s.get("efficiency"),
        "avg_hrv":    s.get("average_hrv"),
        "avg_hr":     s.get("average_heart_rate"),
    }


# ── Garmin ─────────────────────────────────────────────────────────────────────

def garmin_client():
    c = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    try:
        c.login(GARMIN_HOME)
    except Exception:
        c.login()
        c.garth.dump(GARMIN_HOME)
    return c


def fetch_garmin(d):
    c        = garmin_client()
    stats    = c.get_stats(d)        or {}
    sleep_r  = c.get_sleep_data(d)   or {}
    hrv_r    = c.get_hrv_data(d)     or {}
    acts_raw = c.get_activities_by_date(d, d) or []

    sleep_dto = sleep_r.get("dailySleepDTO", {})
    hrv_sum   = hrv_r.get("hrvSummary", {})

    activities = []
    for a in acts_raw:
        dist_m  = a.get("distance") or 0
        dur_s   = a.get("duration") or 0
        dist_km = round(dist_m / 1000, 2)
        dur_min = round(dur_s / 60, 1)
        pace    = round(dur_min / dist_km, 2) if dist_km > 0 else None
        activities.append({
            "name":    a.get("activityName", ""),
            "type":    a.get("activityType", {}).get("typeKey", ""),
            "dist_km": dist_km,
            "dur_min": dur_min,
            "pace":    pace,
            "avg_hr":  a.get("averageHR"),
        })

    garmin = {
        "steps":      stats.get("totalSteps"),
        "resting_hr": stats.get("restingHeartRate"),
        "avg_stress": stats.get("averageStressLevel"),
        "body_batt":  stats.get("bodyBatteryHighestValue"),
        "hrv":        hrv_sum.get("lastNight"),
        "sleep_hrs":  round(sleep_dto.get("sleepTimeSeconds", 0) / 3600, 2),
        "deep_min":   round(sleep_dto.get("deepSleepSeconds",  0) / 60),
        "rem_min":    round(sleep_dto.get("remSleepSeconds",   0) / 60),
    }
    return garmin, activities


# ── Google Sheets ──────────────────────────────────────────────────────────────

DAILY_HEADERS = [
    "Date",
    "Oura Score", "Oura Sleep Hrs", "Oura Deep (min)", "Oura REM (min)",
    "Oura Light (min)", "Oura Efficiency", "Oura Avg HRV", "Oura Avg HR",
    "Garmin Steps", "Garmin Resting HR", "Garmin HRV", "Garmin Body Battery",
    "Garmin Avg Stress", "Garmin Sleep Hrs", "Garmin Deep (min)", "Garmin REM (min)",
]
ACT_HEADERS = [
    "Date", "Name", "Type", "Distance (km)", "Duration (min)", "Pace (min/km)", "Avg HR",
]


def get_or_create_ws(sh, name, headers):
    try:
        return sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(name, rows=1000, cols=len(headers))
        ws.append_row(headers)
        return ws


def write_sheets(d, oura, garmin, activities):
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)

    ws = get_or_create_ws(sh, "Daily", DAILY_HEADERS)
    ws.append_row([
        d,
        oura.get("score"),     oura.get("total_hrs"), oura.get("deep_min"),
        oura.get("rem_min"),   oura.get("light_min"), oura.get("efficiency"),
        oura.get("avg_hrv"),   oura.get("avg_hr"),
        garmin.get("steps"),   garmin.get("resting_hr"), garmin.get("hrv"),
        garmin.get("body_batt"), garmin.get("avg_stress"), garmin.get("sleep_hrs"),
        garmin.get("deep_min"), garmin.get("rem_min"),
    ])

    if activities:
        ws_a = get_or_create_ws(sh, "Activities", ACT_HEADERS)
        for a in activities:
            ws_a.append_row([
                d, a["name"], a["type"], a["dist_km"],
                a["dur_min"], a["pace"], a["avg_hr"],
            ])


# ── HTML ───────────────────────────────────────────────────────────────────────

_CSS = """
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#f0f4f8;display:flex;align-items:center;justify-content:center;
       min-height:100vh;margin:0}
  .card{background:#fff;border-radius:14px;box-shadow:0 4px 24px rgba(0,0,0,.08);
        padding:40px 48px;max-width:600px;width:100%}
  h1{font-size:1.55rem;color:#1a202c;margin:0 0 4px}
  .sub{color:#718096;margin:0 0 30px;font-size:.95rem}
  .btn{display:inline-block;padding:11px 26px;border-radius:8px;font-size:1rem;
       font-weight:600;cursor:pointer;border:none;text-decoration:none;
       transition:opacity .15s}
  .btn:hover{opacity:.85}
  .primary{background:#4f46e5;color:#fff}
  .secondary{background:#e2e8f0;color:#4a5568}
  .section{margin-bottom:22px}
  .section h3{font-size:.9rem;font-weight:700;color:#4a5568;text-transform:uppercase;
              letter-spacing:.06em;margin:0 0 10px;border-bottom:1px solid #e2e8f0;
              padding-bottom:6px}
  table{width:100%;border-collapse:collapse;font-size:.9rem}
  td{padding:5px 6px}
  td:first-child{color:#718096}
  td:last-child{font-weight:500;text-align:right}
  .alert{padding:12px 16px;border-radius:8px;margin-bottom:20px;font-size:.9rem}
  .err{background:#fff5f5;color:#c53030;border:1px solid #fed7d7}
  .ok{background:#f0fff4;color:#276749;border:1px solid #9ae6b4}
  .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.78rem;
         background:#e9d8fd;color:#553c9a;font-weight:600}
"""

HOME_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<title>Health Sync</title><style>{{ css }}</style></head>
<body><div class="card">
  <h1>Health Sync</h1>
  <p class="sub">Sync Oura + Garmin data → Google Sheets</p>
  {% if error %}<div class="alert err">{{ error }}</div>{% endif %}
  {% if not oura_connected %}
    <p style="margin-bottom:16px;color:#718096;font-size:.95rem">
      Connect your Oura account to get started.
    </p>
    <a href="/connect" class="btn primary">Connect Oura Ring</a>
  {% else %}
    <p style="margin-bottom:20px;color:#48bb78;font-size:.9rem;font-weight:500">
      ✓ Oura connected
    </p>
    <form method="post" action="/sync">
      <button type="submit" class="btn primary">Sync Yesterday ({{ yesterday }})</button>
    </form>
  {% endif %}
</div></body></html>"""

RESULT_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<title>Sync Complete</title><style>{{ css }}</style></head>
<body><div class="card">
  <h1>Sync Complete</h1>
  <p class="sub">{{ date }} · written to Google Sheets</p>
  <div class="alert ok">✓ Daily row written &nbsp;·&nbsp; {{ act_count }} activit{{ "ies" if act_count != 1 else "y" }} written</div>

  <div class="section">
    <h3>Oura Sleep</h3>
    <table>
      <tr><td>Score</td>        <td>{{ oura.score }}</td></tr>
      <tr><td>Total sleep</td>  <td>{{ oura.total_hrs }} hrs</td></tr>
      <tr><td>Deep</td>         <td>{{ oura.deep_min }} min</td></tr>
      <tr><td>REM</td>          <td>{{ oura.rem_min }} min</td></tr>
      <tr><td>Light</td>        <td>{{ oura.light_min }} min</td></tr>
      <tr><td>Efficiency</td>   <td>{{ oura.efficiency }}%</td></tr>
      <tr><td>Avg HRV</td>      <td>{{ oura.avg_hrv }}</td></tr>
    </table>
  </div>

  <div class="section">
    <h3>Garmin</h3>
    <table>
      <tr><td>Steps</td>          <td>{{ garmin.steps }}</td></tr>
      <tr><td>Resting HR</td>     <td>{{ garmin.resting_hr }} bpm</td></tr>
      <tr><td>HRV</td>            <td>{{ garmin.hrv }}</td></tr>
      <tr><td>Body Battery</td>   <td>{{ garmin.body_batt }}</td></tr>
      <tr><td>Avg Stress</td>     <td>{{ garmin.avg_stress }}</td></tr>
      <tr><td>Sleep</td>          <td>{{ garmin.sleep_hrs }} hrs</td></tr>
    </table>
  </div>

  {% if activities %}
  <div class="section">
    <h3>Activities</h3>
    <table>
      <tr style="font-size:.8rem;color:#a0aec0">
        <td>Name</td><td></td><td style="text-align:right">Dist</td>
        <td style="text-align:right">Time</td><td style="text-align:right">Pace</td>
        <td style="text-align:right">HR</td>
      </tr>
      {% for a in activities %}
      <tr>
        <td>{{ a.name }}</td>
        <td><span class="badge">{{ a.type }}</span></td>
        <td>{{ a.dist_km }} km</td>
        <td>{{ a.dur_min }} min</td>
        <td>{{ a.pace }} /km</td>
        <td>{{ a.avg_hr }} bpm</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}

  <a href="/" class="btn secondary" style="margin-top:8px">← Back</a>
</div></body></html>"""

ERROR_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<title>Error</title><style>{{ css }}</style></head>
<body><div class="card">
  <h1>Sync Failed</h1>
  <div class="alert err">{{ message }}</div>
  <a href="/" class="btn secondary">← Back</a>
</div></body></html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(
        HOME_TMPL,
        css=_CSS,
        oura_connected=load_oura_token() is not None,
        yesterday=yesterday(),
        error=request.args.get("error"),
    )


@app.route("/connect")
def connect_oura():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = (
        f"response_type=code"
        f"&client_id={OURA_CLIENT_ID}"
        f"&redirect_uri={OURA_REDIRECT_URI}"
        f"&scope=personal+daily+heartrate+workout+session"
        f"&state={state}"
    )
    return redirect(f"https://cloud.ouraring.com/oauth/authorize?{params}")


@app.route("/callback")
def callback():
    if request.args.get("state") != session.get("oauth_state"):
        return redirect("/?error=Invalid+OAuth+state")

    code = request.args.get("code")
    if not code:
        return redirect("/?error=No+authorization+code+received")

    r = requests.post("https://api.ouraring.com/oauth/token", data={
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": OURA_REDIRECT_URI,
        "client_id":    OURA_CLIENT_ID,
        "client_secret": OURA_CLIENT_SECRET,
    })
    if not r.ok:
        return redirect(f"/?error=Token+exchange+failed:+{r.text[:80]}")

    save_oura_token(r.json())
    return redirect("/")


@app.route("/sync", methods=["POST"])
def sync():
    d = yesterday()
    try:
        oura     = fetch_oura_sleep(d)
        garmin, activities = fetch_garmin(d)
        write_sheets(d, oura, garmin, activities)
    except Exception as e:
        return render_template_string(ERROR_TMPL, css=_CSS, message=str(e))

    return render_template_string(
        RESULT_TMPL,
        css=_CSS,
        date=d,
        oura=oura,
        garmin=garmin,
        activities=activities,
        act_count=len(activities),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
