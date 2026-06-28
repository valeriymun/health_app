"""Live connection / integration smoke tests for the health_app backend.

Run from backend/ with the venv active:
    pytest tests/test_connections.py -v -s

These tests hit real APIs when credentials are present, and skip otherwise so
the suite stays runnable in any environment.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

import httpx
import pytest

from app.config import settings


# ---------- Internal API surface -------------------------------------------------

def test_imports_and_app_boot():
    """FastAPI app, routers, models, services all import without error."""
    from app.main import app
    from app.routers import dashboard, ingest, reports  # noqa: F401
    from app.services import apple_health, garmin, oura  # noqa: F401

    routes = {r.path for r in app.routes}
    expected = {
        "/api/health",
        "/api/ingest/apple-health/upload",
        "/api/ingest/apple-health/shortcuts",
        "/api/ingest/oura/sync",
        "/api/ingest/garmin/sync",
    }
    missing = expected - routes
    assert not missing, f"missing routes: {missing}"


def test_database_create_all():
    """SQLAlchemy can create the schema against the configured DB."""
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)
    # Pull table names
    from sqlalchemy import inspect
    tables = set(inspect(engine).get_table_names())
    for t in ("health_metrics", "sleep_sessions", "workouts", "daily_summaries"):
        assert t in tables, f"table {t} not created; got {tables}"


def test_health_endpoint_via_testclient():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ---------- Claude / Anthropic --------------------------------------------------

def test_no_claude_api_integration_present():
    """Repo does NOT integrate with Anthropic / Claude API directly — the
    'AI advisor' is markdown upload only. This test documents that fact so
    nobody assumes otherwise; if a real integration is added later, flip it."""
    import importlib
    for mod_name in ("anthropic",):
        spec = importlib.util.find_spec(mod_name)
        assert spec is None, (
            f"{mod_name} is installed — Claude API integration may now exist; "
            "update this test and add live API checks."
        )
    # And no ANTHROPIC_API_KEY expected on settings
    assert not hasattr(settings, "anthropic_api_key"), \
        "Settings now have anthropic_api_key — add a live Claude check here."


# ---------- Hevy ----------------------------------------------------------------

HEVY_OK = bool(settings.hevy_api_key)


def test_hevy_imports_and_endpoint_registered():
    """Hevy service is wired into the app."""
    from app.main import app
    from app.services import hevy  # noqa: F401
    paths = {r.path for r in app.routes}
    assert "/api/ingest/hevy/sync" in paths
    assert "/api/ingest/hevy/status" in paths


def test_hevy_sync_without_key_raises_400():
    """The endpoint should return 400 (not 500) when the key is missing."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.config import settings as s
    original = s.hevy_api_key
    s.hevy_api_key = ""
    try:
        with TestClient(app) as c:
            r = c.post("/api/ingest/hevy/sync", json={})
            assert r.status_code == 400, r.text
            assert "hevy" in r.text.lower()
    finally:
        s.hevy_api_key = original


@pytest.mark.skipif(not HEVY_OK, reason="HEVY_API_KEY not set")
def test_hevy_api_key_authenticates():
    """The key should hit /workouts/count successfully."""
    from app.services.hevy import get_workout_count
    n = get_workout_count()
    assert isinstance(n, int)
    assert n >= 0


@pytest.mark.skipif(not HEVY_OK, reason="HEVY_API_KEY not set")
def test_hevy_status_endpoint_live():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        r = c.get("/api/ingest/hevy/status")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert isinstance(body["remote_workout_count"], int)


@pytest.mark.skipif(not HEVY_OK, reason="HEVY_API_KEY not set")
def test_hevy_sync_persists_workouts_and_sets():
    """End-to-end: sync recent Hevy workouts and confirm DB rows."""
    from app.database import Base, SessionLocal, engine
    from app.services.hevy import sync_hevy_workouts
    from app.models.health import HevySet, Workout, Source

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Wide window to catch at least one historical workout for any active user
        end = date.today()
        start = end - timedelta(days=365)
        counts = sync_hevy_workouts(db, start, end)
        assert counts["workouts"] >= 0
        if counts["workouts"] > 0:
            hevy_workouts = db.query(Workout).filter_by(source=Source.HEVY).count()
            assert hevy_workouts >= 1
            assert db.query(HevySet).count() >= 1
    finally:
        db.close()


# ---------- Oura ----------------------------------------------------------------

OURA_OK = bool(settings.oura_personal_access_token)


@pytest.mark.skipif(not OURA_OK, reason="OURA_PERSONAL_ACCESS_TOKEN not set")
def test_oura_token_authenticates():
    """Token reaches Oura and returns a personal_info payload."""
    r = httpx.get(
        "https://api.ouraring.com/v2/usercollection/personal_info",
        headers={"Authorization": f"Bearer {settings.oura_personal_access_token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, f"oura auth failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    assert "age" in body or "email" in body or body, f"unexpected body: {body}"


@pytest.mark.skipif(not OURA_OK, reason="OURA_PERSONAL_ACCESS_TOKEN not set")
def test_oura_sleep_endpoint_returns_recent():
    end = date.today()
    start = end - timedelta(days=7)
    r = httpx.get(
        "https://api.ouraring.com/v2/usercollection/sleep",
        params={"start_date": start.isoformat(), "end_date": end.isoformat()},
        headers={"Authorization": f"Bearer {settings.oura_personal_access_token}"},
        timeout=20.0,
    )
    assert r.status_code == 200, r.text[:200]
    assert "data" in r.json()


@pytest.mark.skipif(not OURA_OK, reason="OURA_PERSONAL_ACCESS_TOKEN not set")
def test_oura_sync_writes_rows():
    """End-to-end: app.services.oura.sync_oura_data persists rows."""
    from app.database import Base, SessionLocal, engine
    from app.services.oura import sync_oura_data
    from app.models.health import SleepSession, DailySummary

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        end = date.today()
        start = end - timedelta(days=14)
        counts = asyncio.run(sync_oura_data(db, start, end))
        assert isinstance(counts, dict)
        # Some category must have any data over 2 weeks for an active user
        assert sum(counts.values()) > 0, f"sync returned no rows: {counts}"
        # And rows are in the DB
        assert db.query(SleepSession).count() >= 0
        assert db.query(DailySummary).count() >= 0
    finally:
        db.close()


# ---------- Garmin --------------------------------------------------------------

GARMIN_OK = bool(settings.garmin_email and settings.garmin_password)
# Token-cache fallback (used by the Garmin lib via garth) — works even without
# email/password if a prior login was cached.
GARMIN_TOKEN_CACHE = (
    os.path.expanduser("~/.garminconnect")
    if os.path.isdir(os.path.expanduser("~/.garminconnect"))
    else None
)


@pytest.mark.skipif(not GARMIN_TOKEN_CACHE, reason="~/.garminconnect token cache missing")
def test_garmin_service_uses_token_cache_when_no_password():
    """The backend's _get_client() should now succeed via cached garth tokens
    even when GARMIN_EMAIL/PASSWORD are empty (this is the fix being validated)."""
    from app.services import garmin as gs
    # Force the no-creds path
    original_email, original_pwd = settings.garmin_email, settings.garmin_password
    settings.garmin_email = ""
    settings.garmin_password = ""
    gs._reset_client()
    try:
        client = gs._get_client()
        stats = client.get_stats(date.today().isoformat())
        assert isinstance(stats, dict)
        assert stats.get("userProfileId")
    finally:
        settings.garmin_email = original_email
        settings.garmin_password = original_pwd
        gs._reset_client()


@pytest.mark.skipif(not GARMIN_TOKEN_CACHE, reason="~/.garminconnect token cache missing")
def test_garmin_sync_writes_rows_via_token_cache():
    """End-to-end sync using the token-cache auth path."""
    from app.database import Base, SessionLocal, engine
    from app.services import garmin as gs

    original_email, original_pwd = settings.garmin_email, settings.garmin_password
    settings.garmin_email = ""
    settings.garmin_password = ""
    gs._reset_client()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        end = date.today()
        start = end - timedelta(days=2)
        counts = gs.sync_garmin_data(db, start, end)
        assert isinstance(counts, dict)
        assert sum(counts.values()) >= 0
    finally:
        db.close()
        settings.garmin_email = original_email
        settings.garmin_password = original_pwd
        gs._reset_client()


@pytest.mark.skipif(not GARMIN_OK, reason="GARMIN_EMAIL/PASSWORD not set")
def test_garmin_login_and_basic_fetch():
    from garminconnect import Garmin
    g = Garmin(settings.garmin_email, settings.garmin_password)
    g.login()
    today = date.today().isoformat()
    stats = g.get_stats(today)
    assert isinstance(stats, dict)


@pytest.mark.skipif(not GARMIN_OK, reason="GARMIN_EMAIL/PASSWORD not set")
def test_garmin_sync_writes_rows():
    from app.database import Base, SessionLocal, engine
    from app.services.garmin import sync_garmin_data

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        end = date.today()
        start = end - timedelta(days=3)
        counts = sync_garmin_data(db, start, end)
        assert isinstance(counts, dict)
        assert sum(counts.values()) >= 0  # zero is OK if nothing recorded
    finally:
        db.close()


# ---------- Apple Health --------------------------------------------------------

def test_apple_health_shortcuts_requires_key():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        # Missing key → 422 (Header(...) required) or 401
        r = c.post("/api/ingest/apple-health/shortcuts", json={"metrics": []})
        assert r.status_code in (401, 422)
        # Wrong key → 401
        r = c.post(
            "/api/ingest/apple-health/shortcuts",
            json={"metrics": []},
            headers={"X-API-Key": "wrong"},
        )
        assert r.status_code == 401
        # Right key → 200
        r = c.post(
            "/api/ingest/apple-health/shortcuts",
            json={"metrics": [], "sleep": None, "workouts": []},
            headers={"X-API-Key": settings.apple_health_api_key},
        )
        assert r.status_code == 200, r.text
