"""Oura Ring API v2 integration service."""

from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.health import (
    DailySummary,
    HealthMetric,
    MetricType,
    SleepSession,
    SleepStage,
    Source,
)

OURA_BASE_URL = "https://api.ouraring.com/v2/usercollection"


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.oura_personal_access_token}"}


async def _fetch_paginated(client: httpx.AsyncClient, endpoint: str, params: dict) -> list:
    """Fetch all pages from an Oura API endpoint."""
    all_data = []
    url = f"{OURA_BASE_URL}/{endpoint}"

    while url:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        body = resp.json()
        all_data.extend(body.get("data", []))
        url = body.get("next_token")
        if url:
            params["next_token"] = url
            url = f"{OURA_BASE_URL}/{endpoint}"

    return all_data


async def sync_oura_data(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Sync all data from Oura Ring API."""
    if not settings.oura_personal_access_token:
        raise ValueError("Oura personal access token not configured")

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    counts = {"sleep": 0, "daily": 0, "metrics": 0}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Sync sleep data
        sleep_data = await _fetch_paginated(client, "sleep", params)
        for s in sleep_data:
            source_id = f"oura_sleep_{s.get('id', s.get('day', ''))}"
            existing = db.query(SleepSession).filter_by(source_id=source_id).first()
            if existing:
                continue

            session = SleepSession(
                date=s.get("day", ""),
                bedtime=datetime.fromisoformat(s["bedtime_start"])
                if s.get("bedtime_start")
                else None,
                wake_time=datetime.fromisoformat(s["bedtime_end"])
                if s.get("bedtime_end")
                else None,
                total_sleep_minutes=s.get("total_sleep_duration", 0) // 60
                if s.get("total_sleep_duration")
                else None,
                deep_sleep_minutes=s.get("deep_sleep_duration", 0) // 60
                if s.get("deep_sleep_duration")
                else None,
                rem_sleep_minutes=s.get("rem_sleep_duration", 0) // 60
                if s.get("rem_sleep_duration")
                else None,
                light_sleep_minutes=s.get("light_sleep_duration", 0) // 60
                if s.get("light_sleep_duration")
                else None,
                awake_minutes=s.get("awake_time", 0) // 60
                if s.get("awake_time")
                else None,
                efficiency=s.get("efficiency"),
                avg_heart_rate=s.get("average_heart_rate"),
                avg_hrv=s.get("average_hrv"),
                lowest_heart_rate=s.get("lowest_heart_rate"),
                avg_respiratory_rate=s.get("average_breath"),
                source=Source.OURA,
                source_id=source_id,
            )
            db.add(session)
            counts["sleep"] += 1

        # Sync daily readiness
        readiness_data = await _fetch_paginated(client, "daily_readiness", params)
        for r in readiness_data:
            day = r.get("day", "")
            existing = (
                db.query(DailySummary)
                .filter_by(date=day, source=Source.OURA)
                .first()
            )
            if existing:
                existing.readiness_score = r.get("score")
            else:
                summary = DailySummary(
                    date=day,
                    readiness_score=r.get("score"),
                    source=Source.OURA,
                )
                db.add(summary)
            counts["daily"] += 1

        # Sync daily activity
        activity_data = await _fetch_paginated(client, "daily_activity", params)
        for a in activity_data:
            day = a.get("day", "")
            existing = (
                db.query(DailySummary)
                .filter_by(date=day, source=Source.OURA)
                .first()
            )
            if existing:
                existing.steps = a.get("steps")
                existing.calories_active = a.get("active_calories")
                existing.calories_total = a.get("total_calories")
                existing.activity_score = a.get("score")
            else:
                summary = DailySummary(
                    date=day,
                    steps=a.get("steps"),
                    calories_active=a.get("active_calories"),
                    calories_total=a.get("total_calories"),
                    activity_score=a.get("score"),
                    source=Source.OURA,
                )
                db.add(summary)
            counts["daily"] += 1

        # Sync daily sleep scores
        sleep_score_data = await _fetch_paginated(client, "daily_sleep", params)
        for ss in sleep_score_data:
            day = ss.get("day", "")
            existing = (
                db.query(DailySummary)
                .filter_by(date=day, source=Source.OURA)
                .first()
            )
            if existing:
                existing.sleep_score = ss.get("score")
            counts["daily"] += 1

        # Sync heart rate data
        hr_data = await _fetch_paginated(client, "heartrate", params)
        for hr in hr_data:
            source_id = f"oura_hr_{hr.get('timestamp', '')}"
            metric = HealthMetric(
                metric_type=MetricType.HEART_RATE,
                value=hr.get("bpm", 0),
                unit="bpm",
                timestamp=datetime.fromisoformat(hr["timestamp"]),
                source=Source.OURA,
                source_id=source_id,
            )
            db.add(metric)
            counts["metrics"] += 1

    db.commit()
    return counts


async def sync_oura_full_history(db: Session) -> dict:
    """Sync all available Oura data (from 2015 onward)."""
    return await sync_oura_data(
        db,
        start_date=date(2015, 1, 1),
        end_date=date.today(),
    )
