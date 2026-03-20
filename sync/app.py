#!/usr/bin/env python3
"""
Health Sync — Flask app.

Routes:
  GET  /           Home (Connect or Sync button)
  GET  /connect    Start Oura OAuth2 flow  (also used for re-auth)
  GET  /callback   Oura OAuth2 callback
  POST /sync       Run sync, show result
  GET  /sync       Redirect home
"""

import os
import secrets
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, session
import requests

# Load .env from repo root (one level up from sync/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add sync/ to path so runner/oura_client/etc are importable
sys.path.insert(0, os.path.dirname(__file__))
import oura_client
import runner

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

OURA_CLIENT_ID    = os.getenv("OURA_CLIENT_ID")
OURA_CLIENT_SECRET = os.getenv("OURA_CLIENT_SECRET")
OURA_REDIRECT_URI = "http://localhost:5000/callback"
GOOGLE_SHEET_ID   = os.getenv("GOOGLE_SHEET_ID")


def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#f0f4f8;display:flex;align-items:center;justify-content:center;
     min-height:100vh;margin:0}
.card{background:#fff;border-radius:14px;box-shadow:0 4px 24px rgba(0,0,0,.08);
      padding:36px 44px;max-width:640px;width:100%}
h1{font-size:1.5rem;color:#1a202c;margin:0 0 4px}
.sub{color:#718096;margin:0 0 28px;font-size:.93rem}
.btn{display:inline-block;padding:10px 24px;border-radius:8px;font-size:.97rem;
     font-weight:600;cursor:pointer;border:none;text-decoration:none;
     transition:opacity .15s;margin-right:8px}
.btn:hover{opacity:.82}
.primary{background:#4f46e5;color:#fff}
.secondary{background:#e2e8f0;color:#4a5568}
.ghost{background:none;color:#4f46e5;border:1px solid #c7d2fe;padding:7px 16px;
       font-size:.85rem}
.section{margin-bottom:18px}
.section h3{font-size:.82rem;font-weight:700;color:#4a5568;text-transform:uppercase;
            letter-spacing:.07em;margin:0 0 8px;border-bottom:1px solid #e2e8f0;
            padding-bottom:5px}
table{width:100%;border-collapse:collapse;font-size:.88rem}
td{padding:4px 6px}
td:first-child{color:#718096;width:55%}
td:last-child{font-weight:500;text-align:right}
.row-ok{color:#276749}
.row-skip{color:#a0aec0;font-style:italic}
.alert{padding:11px 15px;border-radius:8px;margin-bottom:16px;font-size:.88rem}
.err{background:#fff5f5;color:#c53030;border:1px solid #fed7d7}
.warn{background:#fffff0;color:#744210;border:1px solid #faf089}
.ok{background:#f0fff4;color:#276749;border:1px solid #9ae6b4}
.badge{display:inline-block;padding:1px 7px;border-radius:4px;font-size:.76rem;
       background:#e9d8fd;color:#553c9a;font-weight:600}
.muted{color:#a0aec0;font-size:.85rem}
"""

# ── Templates ─────────────────────────────────────────────────────────────────

HOME_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<title>Health Sync</title><style>{{ css }}</style></head>
<body><div class="card">
  <h1>Health Sync</h1>
  <p class="sub">Oura Ring + Garmin → Google Sheets</p>

  {% if error %}<div class="alert err">{{ error }}</div>{% endif %}
  {% for w in warnings %}<div class="alert warn">⚠ {{ w }}</div>{% endfor %}

  {% if not oura_connected %}
    <p style="margin-bottom:16px;color:#718096;font-size:.93rem">
      Connect your Oura account to get started.
    </p>
    <a href="/connect" class="btn primary">Connect Oura Ring</a>
  {% else %}
    <p style="margin-bottom:18px;color:#48bb78;font-size:.88rem;font-weight:500">
      ✓ Oura connected
    </p>
    <form method="post" action="/sync" style="display:inline">
      <button type="submit" class="btn primary">Sync Last Night ({{ yesterday }})</button>
    </form>
    <a href="/connect" class="btn ghost" style="margin-left:4px">Re-authorize Oura</a>
  {% endif %}
</div></body></html>"""


RESULT_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<title>Sync Complete</title><style>{{ css }}</style></head>
<body><div class="card">
  <h1>Sync {% if result.status == 'ok' %}Complete{% elif result.status == 'partial' %}Partial{% else %}Failed{% endif %}</h1>
  <p class="sub">{{ result.date }} · {{ result.finished_at[:19] }} UTC</p>

  {% if result.warnings %}
    {% for w in result.warnings %}
      <div class="alert warn">⚠ {{ w }}</div>
    {% endfor %}
  {% endif %}

  {% if result.errors and result.status != 'ok' %}
    <div class="alert err">
      {% for e in result.errors %}<div>{{ e }}</div>{% endfor %}
    </div>
  {% endif %}

  <div class="section">
    <h3>Sheets Written</h3>
    <table>
      {% for tab, info in result.sections.items() %}
      <tr class="{{ 'row-skip' if info.error else 'row-ok' }}">
        <td>{{ tab }}</td>
        <td>
          {% if info.error %}
            ✗ {{ info.error[:60] }}
          {% else %}
            {% if info.get('rows', 0) == 0 %}
              — no data
            {% else %}
              ✓ {{ info.get('rows', 0) }} row{{ 's' if info.get('rows',0) != 1 else '' }}
              ({{ info.get('updated',0) }} updated · {{ info.get('inserted',0) }} new)
            {% endif %}
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </table>
  </div>

  {% set ga = result.sections.get('Garmin_Activities', {}) %}
  {% if ga.get('summary') and ga.summary.count %}
  <div class="section">
    <h3>Garmin Activities</h3>
    <table>
      <tr><td>Count</td>         <td>{{ ga.summary.count }}</td></tr>
      <tr><td>Total distance</td><td>{{ ga.summary.dist_km }} km</td></tr>
      <tr><td>Total duration</td><td>{{ ga.summary.dur_min }} min</td></tr>
    </table>
  </div>
  {% endif %}

  <a href="/" class="btn secondary" style="margin-top:8px">← Back</a>
</div></body></html>"""


ERROR_TMPL = """<!doctype html><html><head><meta charset="utf-8">
<title>Sync Error</title><style>{{ css }}</style></head>
<body><div class="card">
  <h1>Sync Failed</h1>
  <div class="alert err" style="white-space:pre-wrap;font-size:.82rem">{{ message }}</div>
  <a href="/" class="btn secondary">← Back</a>
</div></body></html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    warnings = []
    token = oura_client.load_token()
    return render_template_string(
        HOME_TMPL,
        css=_CSS,
        oura_connected=token is not None,
        yesterday=yesterday(),
        error=request.args.get("error"),
        warnings=warnings,
    )


@app.route("/connect")
def connect_oura():
    """Start (or re-start) the Oura OAuth2 flow with full scope set."""
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = (
        f"response_type=code"
        f"&client_id={OURA_CLIENT_ID}"
        f"&redirect_uri={OURA_REDIRECT_URI}"
        f"&scope={oura_client.REQUIRED_SCOPES.replace(' ', '+')}"
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
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  OURA_REDIRECT_URI,
        "client_id":     OURA_CLIENT_ID,
        "client_secret": OURA_CLIENT_SECRET,
    })
    if not r.ok:
        return redirect(f"/?error=Token+exchange+failed:+{r.text[:80]}")

    oura_client.save_token(r.json())
    return redirect("/")


@app.route("/sync", methods=["GET", "POST"])
def sync():
    if request.method == "GET":
        return redirect("/")

    try:
        result = runner.run(yesterday(), GOOGLE_SHEET_ID)
    except Exception:
        import traceback
        return render_template_string(
            ERROR_TMPL, css=_CSS, message=traceback.format_exc()
        )

    return render_template_string(RESULT_TMPL, css=_CSS, result=result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
