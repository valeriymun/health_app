"""Garmin Connect integration service using garminconnect library.

Authentication order:
  1. Cached `garth` tokens at ``settings.garmin_token_store`` (default
     ``~/.garminconnect``). This avoids re-entering credentials and survives MFA.
  2. Email/password from settings (``GARMIN_EMAIL`` / ``GARMIN_PASSWORD``).
     On a successful password login the tokens are dumped to the token store
     so subsequent runs use path (1).

The module-level client is dropped on any error so the next call re-auths
cleanly instead of reusing a poisoned session.
"""

import os
from datetime import date, datetime, timedelta

from garminconnect import Garmin
from sqlalchemy.orm import Session

from app.config import settings
from app.models.health import (
    DailySummary,
    HealthMetric,
    MetricType,
    SleepSession,
    Source,
    Workout,
)

_garmin_client: Garmin | None = None


def _token_store_path() -> str:
    return os.path.expanduser(settings.garmin_token_store or "~/.garminconnect")


def _try_token_login() -> Garmin | None:
    """Attempt to log in using cached garth tokens. Returns client or None."""
    path = _token_store_path()
    if not os.path.isdir(path):
        return None
    try:
        client = Garmin()
        # garminconnect.login(tokenstore=...) loads cached oauth1/oauth2 tokens.
        client.login(path)
        return client
    except Exception:
        return None


def _password_login() -> Garmin:
    if not settings.garmin_email or not settings.garmin_password:
        raise ValueError(
            "Garmin auth failed: no cached tokens at "
            f"{_token_store_path()} and GARMIN_EMAIL/PASSWORD not set"
        )
    client = Garmin(settings.garmin_email, settings.garmin_password)
    client.login()
    # Persist tokens for next time so we can skip the password path.
    try:
        os.makedirs(_token_store_path(), exist_ok=True)
        client.garth.dump(_token_store_path())
    except Exception:
        pass  # token caching is best-effort; auth still succeeded
    return client


def _get_client() -> Garmin:
    global _garmin_client
    if _garmin_client is not None:
        return _garmin_client
    client = _try_token_login() or _password_login()
    _garmin_client = client
    return _garmin_client


def _reset_client():
    global _garmin_client
    _garmin_client = None


def sync_garmin_data(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Sync data from Garmin Connect."""
    try:
        client = _get_client()
        # Cheap call to confirm the session is alive; reset on failure.
        client.get_full_name()
    except Exception:
        _reset_client()
        client = _get_client()

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    counts = {"daily": 0, "sleep": 0, "workouts": 0, "metrics": 0}

    current = start_date
    while current <= end_date:
        date_str = current.isoformat()

        # Daily summary stats
        try:
            stats = client.get_stats(date_str)
            if stats:
                existing = (
                    db.query(DailySummary)
                    .filter_by(date=date_str, source=Source.GARMIN)
                    .first()
                )
                summary_data = dict(
                    steps=stats.get("totalSteps"),
                    calories_active=stats.get("activeKilocalories"),
                    calories_total=stats.get("totalKilocalories"),
                    distance_km=(stats.get("totalDistanceMeters") or 0) / 1000
                    if stats.get("totalDistanceMeters")
                    else None,
                    floors_climbed=stats.get("floorsAscended"),
                    resting_heart_rate=stats.get("restingHeartRate"),
                    avg_stress=stats.get("averageStressLevel"),
                    body_battery_high=stats.get("bodyBatteryHighestValue"),
                    body_battery_low=stats.get("bodyBatteryLowestValue"),
                    spo2_avg=stats.get("averageSpo2"),
                    respiratory_rate=stats.get("averageRespirationValue"),
                )
                if existing:
                    for k, v in summary_data.items():
                        if v is not None:
                            setattr(existing, k, v)
                else:
                    db.add(DailySummary(date=date_str, source=Source.GARMIN, **summary_data))
                counts["daily"] += 1
        except Exception:
            pass

        # Sleep data
        try:
            sleep = client.get_sleep_data(date_str)
            if sleep and sleep.get("dailySleepDTO"):
                s = sleep["dailySleepDTO"]
                source_id = f"garmin_sleep_{date_str}"
                existing = db.query(SleepSession).filter_by(source_id=source_id).first()
                if not existing:
                    session = SleepSession(
                        date=date_str,
                        bedtime=datetime.fromtimestamp(s["sleepStartTimestampGMT"] / 1000)
                        if s.get("sleepStartTimestampGMT")
                        else None,
                        wake_time=datetime.fromtimestamp(s["sleepEndTimestampGMT"] / 1000)
                        if s.get("sleepEndTimestampGMT")
                        else None,
                        total_sleep_minutes=(s.get("sleepTimeSeconds") or 0) // 60
                        if s.get("sleepTimeSeconds")
                        else None,
                        deep_sleep_minutes=(s.get("deepSleepSeconds") or 0) // 60
                        if s.get("deepSleepSeconds")
                        else None,
                        rem_sleep_minutes=(s.get("remSleepSeconds") or 0) // 60
                        if s.get("remSleepSeconds")
                        else None,
                        light_sleep_minutes=(s.get("lightSleepSeconds") or 0) // 60
                        if s.get("lightSleepSeconds")
                        else None,
                        awake_minutes=(s.get("awakeSleepSeconds") or 0) // 60
                        if s.get("awakeSleepSeconds")
                        else None,
                        avg_hrv=s.get("averageHRV"),
                        avg_respiratory_rate=s.get("averageRespirationValue"),
                        source=Source.GARMIN,
                        source_id=source_id,
                    )
                    db.add(session)
                    counts["sleep"] += 1
        except Exception:
            pass

        # Heart rate data
        try:
            hr_data = client.get_heart_rates(date_str)
            if hr_data and hr_data.get("heartRateValues"):
                for ts, bpm in hr_data["heartRateValues"]:
                    if bpm and bpm > 0:
                        metric = HealthMetric(
                            metric_type=MetricType.HEART_RATE,
                            value=bpm,
                            unit="bpm",
                            timestamp=datetime.fromtimestamp(ts / 1000),
                            source=Source.GARMIN,
                            source_id=f"garmin_hr_{ts}",
                        )
                        db.add(metric)
                        counts["metrics"] += 1
        except Exception:
            pass

        current += timedelta(days=1)

    # Workouts/Activities
    try:
        activities = client.get_activities_by_date(
            start_date.isoformat(), end_date.isoformat()
        )
        for a in activities or []:
            source_id = f"garmin_activity_{a.get('activityId', '')}"
            existing = db.query(Workout).filter_by(source_id=source_id).first()
            if existing:
                continue

            workout = Workout(
                activity_type=a.get("activityType", {}).get("typeKey", "unknown"),
                start_time=datetime.fromisoformat(a["startTimeLocal"])
                if a.get("startTimeLocal")
                else datetime.now(),
                duration_minutes=(a.get("duration") or 0) / 60,
                calories=a.get("calories"),
                distance_km=(a.get("distance") or 0) / 1000
                if a.get("distance")
                else None,
                avg_heart_rate=a.get("averageHR"),
                max_heart_rate=a.get("maxHR"),
                elevation_gain=a.get("elevationGain"),
                training_effect_aerobic=a.get("aerobicTrainingEffect"),
                training_effect_anaerobic=a.get("anaerobicTrainingEffect"),
                vo2_max=a.get("vO2MaxValue"),
                source=Source.GARMIN,
                source_id=source_id,
            )
            db.add(workout)
            counts["workouts"] += 1
    except Exception:
        pass

    db.commit()
    return counts


def sync_garmin_full_history(db: Session) -> dict:
    """Sync all available Garmin data. Goes back day by day up to 5 years."""
    return sync_garmin_data(
        db,
        start_date=date.today() - timedelta(days=365 * 5),
        end_date=date.today(),
    )
