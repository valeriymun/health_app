"""Analytical insight endpoints for the Trends tab."""

import math
import statistics
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.health import BacReading, DailySummary, SleepSession

router = APIRouter(prefix="/api/insights", tags=["insights"])

# ─── Widmark constants ─────────────────────────────────────────────────────────
_BODY_WEIGHT_KG = 73.0
_WIDMARK_R = 0.68
_GRAMS_PER_UK_UNIT = 8.0
_ELIMINATION_RATE = 0.015  # % BAC per hour


def _cohens_d(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    mean_a = statistics.mean(a)
    mean_b = statistics.mean(b)
    # pooled SD
    if len(a) < 2 or len(b) < 2:
        pooled = statistics.stdev(a + b) if len(a + b) >= 2 else 1.0
    else:
        pooled = math.sqrt(
            (statistics.variance(a) * (len(a) - 1) + statistics.variance(b) * (len(b) - 1))
            / (len(a) + len(b) - 2)
        )
    return (mean_a - mean_b) / pooled if pooled else 0.0


def _median(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def _sleep_rows(db: Session, since: date, until: date) -> list[SleepSession]:
    return (
        db.query(SleepSession)
        .filter(
            SleepSession.date >= since.isoformat(),
            SleepSession.date <= until.isoformat(),
        )
        .order_by(SleepSession.date.desc())
        .all()
    )


def _daily_rows(db: Session, since: date, until: date) -> list[DailySummary]:
    return (
        db.query(DailySummary)
        .filter(
            DailySummary.date >= since.isoformat(),
            DailySummary.date <= until.isoformat(),
        )
        .order_by(DailySummary.date.desc())
        .all()
    )


# ─── Regime shift ─────────────────────────────────────────────────────────────

@router.get("/regime-shift")
async def regime_shift(
    metric: str = Query("hrv", description="hrv | sleep | rhr | readiness"),
    window_days: int = Query(14),
    baseline_days: int = Query(60),
    db: Session = Depends(get_db),
):
    today = date.today()
    recent_start = today - timedelta(days=window_days)
    baseline_start = today - timedelta(days=baseline_days)

    METRIC_CONFIG = {
        "hrv": ("HRV", "ms", lambda r: r.avg_hrv),
        "sleep": ("Sleep duration", "h", lambda r: r.total_sleep_minutes / 60 if r.total_sleep_minutes else None),
        "rhr": ("Resting HR", "bpm", lambda r: r.lowest_heart_rate),
        "readiness": ("Readiness", "", None),
    }

    label, unit, sleep_getter = METRIC_CONFIG.get(metric, METRIC_CONFIG["hrv"])

    if metric in ("hrv", "sleep", "rhr"):
        recent_rows = _sleep_rows(db, recent_start, today)
        baseline_rows = _sleep_rows(db, baseline_start, today)
        getter = sleep_getter
        recent_vals = [v for r in recent_rows if (v := getter(r)) is not None]
        baseline_vals = [v for r in baseline_rows if (v := getter(r)) is not None]
    else:
        recent_daily = _daily_rows(db, recent_start, today)
        baseline_daily = _daily_rows(db, baseline_start, today)
        if metric == "readiness":
            recent_vals = [r.readiness_score for r in recent_daily if r.readiness_score]
            baseline_vals = [r.readiness_score for r in baseline_daily if r.readiness_score]
        else:
            recent_vals = []
            baseline_vals = []

    d = _cohens_d(recent_vals, baseline_vals)

    return {
        "shift_detected": abs(d) > 0.5,
        "metric": metric,
        "metric_label": label,
        "unit": unit,
        "cohens_d": round(d, 3),
        "recent_median": round(_median(recent_vals) or 0, 2),
        "baseline_median": round(_median(baseline_vals) or 0, 2),
        "recent_n": len(recent_vals),
        "baseline_n": len(baseline_vals),
    }


# ─── Year over year ───────────────────────────────────────────────────────────

def _fmt(val: Optional[float], unit: str) -> str:
    if val is None:
        return "—"
    if unit == "h":
        return f"{val:.1f}h"
    return f"{val:.0f}"


def _direction(now: Optional[float], then: Optional[float], higher_is_better: bool) -> str:
    if now is None or then is None:
        return "same"
    delta = now - then
    if abs(delta) < 0.05 * (abs(then) or 1):
        return "same"
    better = delta > 0 if higher_is_better else delta < 0
    return "better" if better else "worse"


@router.get("/year-over-year")
async def year_over_year(
    days: int = Query(28),
    db: Session = Depends(get_db),
):
    today = date.today()
    now_start = today - timedelta(days=days)
    year_ago = today.replace(year=today.year - 1)
    then_start = year_ago - timedelta(days=days)

    sleep_now = _sleep_rows(db, now_start, today)
    sleep_then = _sleep_rows(db, then_start, year_ago)
    daily_now = _daily_rows(db, now_start, today)
    daily_then = _daily_rows(db, then_start, year_ago)

    def avg_sleep(rows, getter):
        vals = [v for r in rows if (v := getter(r)) is not None]
        return statistics.mean(vals) if vals else None

    def avg_daily(rows, field):
        vals = [v for r in rows if (v := getattr(r, field, None)) is not None]
        return statistics.mean(vals) if vals else None

    rows = [
        {
            "label": "Sleep duration",
            "metric": "sleep",
            "now": _fmt(avg_sleep(sleep_now, lambda r: r.total_sleep_minutes / 60 if r.total_sleep_minutes else None), "h"),
            "last_year": _fmt(avg_sleep(sleep_then, lambda r: r.total_sleep_minutes / 60 if r.total_sleep_minutes else None), "h"),
            "direction": _direction(
                avg_sleep(sleep_now, lambda r: r.total_sleep_minutes / 60 if r.total_sleep_minutes else None),
                avg_sleep(sleep_then, lambda r: r.total_sleep_minutes / 60 if r.total_sleep_minutes else None),
                True,
            ),
        },
        {
            "label": "HRV",
            "metric": "hrv",
            "now": _fmt(avg_sleep(sleep_now, lambda r: r.avg_hrv), "") + "ms",
            "last_year": _fmt(avg_sleep(sleep_then, lambda r: r.avg_hrv), "") + "ms",
            "direction": _direction(
                avg_sleep(sleep_now, lambda r: r.avg_hrv),
                avg_sleep(sleep_then, lambda r: r.avg_hrv),
                True,
            ),
        },
        {
            "label": "Resting HR",
            "metric": "rhr",
            "now": _fmt(avg_daily(daily_now, "resting_heart_rate"), ""),
            "last_year": _fmt(avg_daily(daily_then, "resting_heart_rate"), ""),
            "direction": _direction(
                avg_daily(daily_now, "resting_heart_rate"),
                avg_daily(daily_then, "resting_heart_rate"),
                False,
            ),
        },
        {
            "label": "Readiness",
            "metric": "readiness",
            "now": _fmt(avg_daily(daily_now, "readiness_score"), ""),
            "last_year": _fmt(avg_daily(daily_then, "readiness_score"), ""),
            "direction": _direction(
                avg_daily(daily_now, "readiness_score"),
                avg_daily(daily_then, "readiness_score"),
                True,
            ),
        },
    ]

    return {"days": days, "rows": rows}


# ─── Consistency ──────────────────────────────────────────────────────────────

@router.get("/consistency")
async def consistency(
    days: int = Query(28),
    db: Session = Depends(get_db),
):
    today = date.today()
    recent_start = today - timedelta(days=days)
    historical_start = today - timedelta(days=365)

    recent_rows = _sleep_rows(db, recent_start, today)
    historical_rows = _sleep_rows(db, historical_start, today)

    def sleep_hours(rows):
        return [r.total_sleep_minutes / 60 for r in rows if r.total_sleep_minutes]

    recent = sleep_hours(recent_rows)
    historical = sleep_hours(historical_rows)

    if not recent:
        return {"percentile": 50, "std_dev": 0, "historical_std": 0, "range_min": 0, "range_max": 0}

    std = statistics.stdev(recent) if len(recent) >= 2 else 0
    hist_std = statistics.stdev(historical) if len(historical) >= 2 else std

    # Bootstrap percentile: what fraction of rolling 28-day windows are wider?
    n_windows = max(len(historical) - days, 1)
    wider = 0
    for i in range(n_windows):
        window = sleep_hours(historical_rows[i: i + days])
        if len(window) >= 2 and statistics.stdev(window) > std:
            wider += 1
    percentile = round((wider / n_windows) * 100)

    return {
        "percentile": percentile,
        "std_dev": round(std, 2),
        "historical_std": round(hist_std, 2),
        "range_min": round(min(recent), 2),
        "range_max": round(max(recent), 2),
    }


# ─── Attribution ──────────────────────────────────────────────────────────────

@router.get("/attribution")
async def attribution(
    days: int = Query(14),
    db: Session = Depends(get_db),
):
    today = date.today()
    recent_start = today - timedelta(days=days)
    prior_start = today - timedelta(days=days * 2)

    recent_sleep = _sleep_rows(db, recent_start, today)
    prior_sleep = _sleep_rows(db, prior_start, recent_start)
    recent_daily = _daily_rows(db, recent_start, today)
    prior_daily = _daily_rows(db, prior_start, recent_start)

    items = []

    def avg_sl(rows, field):
        vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
        return statistics.mean(vals) if vals else None

    def avg_da(rows, field):
        vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
        return statistics.mean(vals) if vals else None

    sleep_now = avg_sl(recent_sleep, "total_sleep_minutes")
    sleep_then = avg_sl(prior_sleep, "total_sleep_minutes")
    if sleep_now and sleep_then:
        delta = (sleep_now - sleep_then) / 60
        if abs(delta) > 0.1:
            # Compare wake-time vs bedtime contribution using timestamps in seconds
            def avg_ts(rows, field):
                vals = [r.timestamp() for r in [getattr(s, field) for s in rows] if r is not None]
                return statistics.mean(vals) if vals else None

            wake_now_ts = avg_ts(recent_sleep, "wake_time")
            wake_then_ts = avg_ts(prior_sleep, "wake_time")
            bed_now_ts = avg_ts(recent_sleep, "bedtime")
            bed_then_ts = avg_ts(prior_sleep, "bedtime")
            note = ""
            if all(v is not None for v in [wake_now_ts, wake_then_ts, bed_now_ts, bed_then_ts]):
                wake_delta = abs(wake_now_ts - wake_then_ts)
                bed_delta = abs(bed_now_ts - bed_then_ts)
                note = f"Mainly from {'later wake time' if wake_delta > bed_delta else 'earlier bedtime'}."
            items.append({"metric": "Sleep duration", "delta": round(delta, 2), "unit": "h", "note": note})

    hrv_now = avg_sl(recent_sleep, "avg_hrv")
    hrv_then = avg_sl(prior_sleep, "avg_hrv")
    if hrv_now and hrv_then:
        delta = hrv_now - hrv_then
        if abs(delta) > 1:
            items.append({"metric": "HRV", "delta": round(delta, 1), "unit": "ms", "note": ""})

    rhr_now = avg_da(recent_daily, "resting_heart_rate")
    rhr_then = avg_da(prior_daily, "resting_heart_rate")
    if rhr_now and rhr_then:
        delta = rhr_now - rhr_then
        if abs(delta) > 0.5:
            items.append({"metric": "Resting HR", "delta": round(delta, 1), "unit": "bpm", "note": ""})

    return {"days": days, "items": items}


# ─── Smart suggestions ────────────────────────────────────────────────────────

@router.get("/smart-suggestions")
async def smart_suggestions(db: Session = Depends(get_db)):
    today = date.today()
    recent_sleep = _sleep_rows(db, today - timedelta(days=14), today)
    recent_daily = _daily_rows(db, today - timedelta(days=14), today)

    suggestions = []

    hrv_vals = [r.avg_hrv for r in recent_sleep if r.avg_hrv]
    if hrv_vals and len(hrv_vals) >= 7:
        d = _cohens_d(hrv_vals[:7], hrv_vals[7:])
        if abs(d) > 0.5:
            suggestions.append("Your HRV shifted — what's driving it?")

    sleep_vals = [r.total_sleep_minutes / 60 for r in recent_sleep if r.total_sleep_minutes]
    if sleep_vals:
        if min(sleep_vals) > 6.5:
            suggestions.append("Sleep floor is at a high — what changed?")
        if statistics.stdev(sleep_vals) < 0.5 if len(sleep_vals) >= 2 else False:
            suggestions.append("Unusually consistent sleep this fortnight.")

    readiness_vals = [r.readiness_score for r in recent_daily if r.readiness_score]
    if readiness_vals and statistics.mean(readiness_vals) < 65:
        suggestions.append("Readiness has been low — check training load or sleep quality.")

    if not suggestions:
        suggestions = [
            "What happened this week?",
            "How did my sleep trend this month?",
            "Compare this week to last week",
        ]

    return {"suggestions": suggestions[:5]}


# ─── BAC budget ───────────────────────────────────────────────────────────────

@router.get("/bac-budget")
async def bac_budget(
    weekly_budget: float = Query(14.0),
    db: Session = Depends(get_db),
):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday

    readings = (
        db.query(BacReading)
        .filter(BacReading.timestamp >= datetime.combine(week_start, datetime.min.time()))
        .order_by(BacReading.timestamp.desc())
        .all()
    )

    units_this_week = sum(r.units for r in readings)

    # Current BAC from most-recent reading
    current_bac = 0.0
    clears_at = None
    if readings:
        latest = readings[0]
        hours_elapsed = (datetime.utcnow() - latest.timestamp).total_seconds() / 3600
        peak_bac = (latest.units * _GRAMS_PER_UK_UNIT) / (_BODY_WEIGHT_KG * _WIDMARK_R * 10)
        current_bac = max(0.0, peak_bac - _ELIMINATION_RATE * hours_elapsed)
        if current_bac > 0:
            hours_to_clear = current_bac / _ELIMINATION_RATE
            clear_time = datetime.utcnow() + timedelta(hours=hours_to_clear)
            clears_at = clear_time.strftime("%H:%M")

    return {
        "drinks_this_week": round(units_this_week, 1),
        "weekly_budget": weekly_budget,
        "current_bac": round(current_bac, 4),
        "clears_at": clears_at,
        "week_start": week_start.isoformat(),
    }


# ─── Log BAC reading ──────────────────────────────────────────────────────────

class BacReadingIn(BaseModel):
    units: float
    timestamp: Optional[str] = None
    notes: Optional[str] = None


@router.post("/bac-reading", status_code=201)
async def log_bac_reading(
    body: BacReadingIn,
    db: Session = Depends(get_db),
):
    ts = datetime.fromisoformat(body.timestamp) if body.timestamp else datetime.utcnow()
    reading = BacReading(units=body.units, timestamp=ts, notes=body.notes)
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return {"id": reading.id, "units": reading.units, "timestamp": reading.timestamp.isoformat()}
