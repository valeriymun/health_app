"""Hevy API v1 sync.

Authoritative for set-level strength data. Each Hevy workout is upserted to
the shared ``workouts`` table (so it shows up alongside Garmin activities in
the dashboard) and its exercises + sets are written to ``hevy_exercises`` /
``hevy_sets`` for set-level analysis.

Docs: https://api.hevyapp.com/docs/
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Iterable

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models.health import HevyExercise, HevySet, Source, Workout

HEVY_BASE = "https://api.hevyapp.com/v1"
PAGE_SIZE = 10  # Hevy API caps page size at 10


def _headers() -> dict[str, str]:
    return {"api-key": settings.hevy_api_key, "Accept": "application/json"}


def _require_key() -> None:
    if not settings.hevy_api_key:
        raise ValueError("Hevy API key not configured (set HEVY_API_KEY)")


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Hevy returns ISO 8601 with Z; fromisoformat handles +00:00 from 3.11
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _upsert_workout(db: Session, w: dict) -> None:
    """Upsert one Hevy workout into Workout + hevy_exercises + hevy_sets."""
    hid = w["id"]
    source_id = f"hevy_workout_{hid}"
    start = _parse_dt(w.get("start_time")) or datetime.utcnow()
    end = _parse_dt(w.get("end_time"))
    duration = (end - start).total_seconds() / 60.0 if end else None

    existing = db.query(Workout).filter_by(source_id=source_id).first()
    fields = dict(
        activity_type="strength",
        start_time=start,
        end_time=end,
        duration_minutes=duration,
        notes=w.get("description") or w.get("title"),
        source=Source.HEVY,
        source_id=source_id,
    )
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        db.add(Workout(**fields))

    # Replace exercises + sets for idempotent re-sync
    db.execute(delete(HevyExercise).where(HevyExercise.workout_id == hid))
    db.execute(delete(HevySet).where(HevySet.workout_id == hid))

    for ex in w.get("exercises", []) or []:
        idx = ex.get("index", 0)
        db.add(HevyExercise(
            workout_id=hid,
            exercise_index=idx,
            title=ex.get("title"),
            exercise_template_id=ex.get("exercise_template_id"),
            superset_id=ex.get("superset_id"),
            notes=ex.get("notes"),
        ))
        for s in ex.get("sets", []) or []:
            db.add(HevySet(
                workout_id=hid,
                exercise_index=idx,
                set_index=s.get("index", 0),
                set_type=s.get("set_type"),
                weight_kg=s.get("weight_kg"),
                reps=s.get("reps"),
                duration_seconds=s.get("duration_seconds"),
                distance_meters=s.get("distance_meters"),
                rpe=s.get("rpe"),
            ))


def _paginate(client: httpx.Client, endpoint: str, extra: dict | None = None) -> Iterable[dict]:
    """Yield raw response bodies page-by-page from a Hevy endpoint."""
    page = 1
    while True:
        params = {"page": page, "pageSize": PAGE_SIZE}
        if extra:
            params.update(extra)
        resp = client.get(f"{HEVY_BASE}/{endpoint}", params=params, headers=_headers())
        resp.raise_for_status()
        body = resp.json()
        yield body
        if page >= body.get("page_count", 1):
            return
        page += 1
        time.sleep(0.5)  # gentle rate limiting; Hevy is ~10 req/s


def sync_hevy_workouts(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Backfill workouts. Date filtering is applied client-side after pagination
    because /workouts has no date params; for true incremental use ``sync_hevy_events``."""
    _require_key()
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    counts = {"workouts": 0, "exercises": 0, "sets": 0}
    with httpx.Client(timeout=30.0) as client:
        for body in _paginate(client, "workouts"):
            for w in body.get("workouts", []):
                start = _parse_dt(w.get("start_time"))
                if start and start.date() < start_date:
                    # Workouts come newest-first; cut once past the window
                    db.commit()
                    return counts
                if start and start.date() > end_date:
                    continue
                _upsert_workout(db, w)
                counts["workouts"] += 1
                counts["exercises"] += len(w.get("exercises") or [])
                counts["sets"] += sum(
                    len(ex.get("sets") or []) for ex in (w.get("exercises") or [])
                )

    db.commit()
    return counts


def sync_hevy_full_history(db: Session) -> dict:
    """Sync ALL workouts ever recorded."""
    _require_key()
    counts = {"workouts": 0, "exercises": 0, "sets": 0}
    with httpx.Client(timeout=30.0) as client:
        for body in _paginate(client, "workouts"):
            for w in body.get("workouts", []):
                _upsert_workout(db, w)
                counts["workouts"] += 1
                counts["exercises"] += len(w.get("exercises") or [])
                counts["sets"] += sum(
                    len(ex.get("sets") or []) for ex in (w.get("exercises") or [])
                )
    db.commit()
    return counts


def get_workout_count() -> int:
    """Total workout count on the Hevy side; useful for health checks."""
    _require_key()
    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{HEVY_BASE}/workouts/count", headers=_headers())
        r.raise_for_status()
        return int(r.json().get("workout_count", 0))
