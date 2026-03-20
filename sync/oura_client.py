"""
Oura Ring v2 API client.

Scopes used: personal daily heartrate workout session spo2

Re-auth note:
  If you originally authorized with the old scope set (without 'spo2'),
  daily_spo2 will return 403 and be silently skipped. To enable SpO2,
  click "Re-authorize Oura" on the home page.
"""

import json
import os
from datetime import date

import requests

OURA_BASE  = "https://api.ouraring.com/v2/usercollection"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "oura_token.json")

# Expanded scope set vs original (added: spo2)
REQUIRED_SCOPES = "personal daily heartrate workout session spo2"


# ── Token management ──────────────────────────────────────────────────────────

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def save_token(t):
    with open(TOKEN_FILE, "w") as f:
        json.dump(t, f)


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _call(access_token, path, params):
    return requests.get(
        f"{OURA_BASE}/{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30,
    )


def _request(path, params=None):
    token = load_token()
    if not token:
        raise RuntimeError("Oura not connected — please authorize first.")

    r = _call(token["access_token"], path, params)

    if r.status_code == 401:
        r2 = requests.post("https://api.ouraring.com/oauth/token", data={
            "grant_type":    "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id":     os.getenv("OURA_CLIENT_ID"),
            "client_secret": os.getenv("OURA_CLIENT_SECRET"),
        })
        if r2.ok:
            token = r2.json()
            save_token(token)
            r = _call(token["access_token"], path, params)
        else:
            raise RuntimeError(f"Token refresh failed: {r2.text[:120]}")

    if r.status_code == 403:
        # Likely a missing scope — caller should surface a re-auth warning
        raise PermissionError(f"/{path} returned 403 — re-authorize Oura to enable this data.")

    if not r.ok:
        raise RuntimeError(f"Oura /{path} → {r.status_code}: {r.text[:120]}")

    return r.json().get("data", [])


def _safe(path, params):
    """Return (data_list, error_str_or_None). Never raises."""
    try:
        return _request(path, params), None
    except PermissionError as e:
        return [], f"SCOPE_MISSING: {e}"
    except Exception as e:
        return [], str(e)


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_all(target_date: str) -> dict:
    """
    Fetch all available Oura data sections for target_date (YYYY-MM-DD).

    Sleep-related endpoints use [target_date, today] because Oura assigns
    each sleep session to the calendar day the user wakes up — which may be
    today for last night's sleep.

    Returns {endpoint_name: (data_list, error_or_None)}.
    Continues fetching remaining sections even if one fails.
    """
    today       = date.today().isoformat()
    sleep_range = {"start_date": target_date, "end_date": today}
    day_range   = {"start_date": target_date, "end_date": target_date}

    return {
        "sleep":            _safe("sleep",            sleep_range),
        "daily_sleep":      _safe("daily_sleep",      sleep_range),
        "daily_readiness":  _safe("daily_readiness",  day_range),
        "daily_activity":   _safe("daily_activity",   day_range),
        "daily_stress":     _safe("daily_stress",     day_range),
        "daily_resilience": _safe("daily_resilience", day_range),
        "daily_spo2":       _safe("daily_spo2",       sleep_range),
    }
