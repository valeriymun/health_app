"""Dashboard API endpoints for health trends and summaries."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.health import (
    DailySummary,
    HealthMetric,
    MetricType,
    SleepSession,
    Workout,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db)):
    """Get a high-level overview of all health data for the dashboard."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Latest daily summaries (last 7 days, any source)
    recent_summaries = (
        db.query(DailySummary)
        .filter(DailySummary.date >= week_ago.isoformat())
        .order_by(DailySummary.date.desc())
        .all()
    )

    # Aggregate by date (merge multiple sources)
    daily_data = {}
    for s in recent_summaries:
        if s.date not in daily_data:
            daily_data[s.date] = {}
        d = daily_data[s.date]
        for field in [
            "steps", "calories_active", "calories_total", "resting_heart_rate",
            "avg_hrv", "avg_stress", "readiness_score", "activity_score",
            "sleep_score", "spo2_avg", "respiratory_rate",
        ]:
            val = getattr(s, field, None)
            if val is not None:
                d[field] = val  # Last source wins for simplicity

    # Recent sleep sessions
    recent_sleep = (
        db.query(SleepSession)
        .filter(SleepSession.date >= week_ago.isoformat())
        .order_by(SleepSession.date.desc())
        .all()
    )

    sleep_data = []
    seen_dates = set()
    for s in recent_sleep:
        if s.date in seen_dates:
            continue
        seen_dates.add(s.date)
        sleep_data.append({
            "date": s.date,
            "total_minutes": s.total_sleep_minutes,
            "deep_minutes": s.deep_sleep_minutes,
            "rem_minutes": s.rem_sleep_minutes,
            "light_minutes": s.light_sleep_minutes,
            "awake_minutes": s.awake_minutes,
            "efficiency": s.efficiency,
            "score": s.sleep_score,
            "avg_hr": s.avg_heart_rate,
            "avg_hrv": s.avg_hrv,
            "bedtime": s.bedtime.isoformat() if s.bedtime else None,
            "wake_time": s.wake_time.isoformat() if s.wake_time else None,
        })

    # Recent workouts
    recent_workouts = (
        db.query(Workout)
        .filter(Workout.start_time >= datetime.combine(week_ago, datetime.min.time()))
        .order_by(Workout.start_time.desc())
        .limit(20)
        .all()
    )

    workout_data = [
        {
            "type": w.activity_type,
            "start": w.start_time.isoformat() if w.start_time else None,
            "duration_minutes": w.duration_minutes,
            "calories": w.calories,
            "distance_km": w.distance_km,
            "avg_hr": w.avg_heart_rate,
            "max_hr": w.max_heart_rate,
        }
        for w in recent_workouts
    ]

    # Data counts
    total_metrics = db.query(func.count(HealthMetric.id)).scalar()
    total_sleep = db.query(func.count(SleepSession.id)).scalar()
    total_workouts = db.query(func.count(Workout.id)).scalar()
    total_days = db.query(func.count(func.distinct(DailySummary.date))).scalar()

    return {
        "daily": [{"date": d, **v} for d, v in sorted(daily_data.items(), reverse=True)],
        "sleep": sleep_data,
        "workouts": workout_data,
        "stats": {
            "total_metrics": total_metrics,
            "total_sleep_sessions": total_sleep,
            "total_workouts": total_workouts,
            "total_days_tracked": total_days,
        },
    }


@router.get("/trends/{metric_type}")
async def get_metric_trend(
    metric_type: MetricType,
    days: int = Query(30, ge=1, le=365),
    aggregation: str = Query("daily_avg", pattern="^(daily_avg|daily_max|daily_min|raw)$"),
    db: Session = Depends(get_db),
):
    """Get trend data for a specific metric over time."""
    since = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())

    if aggregation == "raw":
        metrics = (
            db.query(HealthMetric)
            .filter(
                HealthMetric.metric_type == metric_type,
                HealthMetric.timestamp >= since,
            )
            .order_by(HealthMetric.timestamp)
            .limit(5000)
            .all()
        )
        return {
            "metric": metric_type.value,
            "data": [
                {"timestamp": m.timestamp.isoformat(), "value": m.value, "source": m.source.value}
                for m in metrics
            ],
        }

    # Aggregated query
    agg_func = {"daily_avg": func.avg, "daily_max": func.max, "daily_min": func.min}[aggregation]

    results = (
        db.query(
            func.date(HealthMetric.timestamp).label("day"),
            agg_func(HealthMetric.value).label("value"),
            func.count(HealthMetric.id).label("count"),
        )
        .filter(
            HealthMetric.metric_type == metric_type,
            HealthMetric.timestamp >= since,
        )
        .group_by(func.date(HealthMetric.timestamp))
        .order_by(func.date(HealthMetric.timestamp))
        .all()
    )

    return {
        "metric": metric_type.value,
        "aggregation": aggregation,
        "data": [
            {"date": str(r.day), "value": round(r.value, 2), "sample_count": r.count}
            for r in results
        ],
    }


@router.get("/sleep/trends")
async def get_sleep_trends(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get sleep trends over time."""
    since = (date.today() - timedelta(days=days)).isoformat()

    sessions = (
        db.query(SleepSession)
        .filter(SleepSession.date >= since)
        .order_by(SleepSession.date)
        .all()
    )

    # Deduplicate by date, prefer Oura > Garmin > Apple
    by_date = {}
    source_priority = {"oura": 0, "garmin": 1, "apple_health": 2}
    for s in sessions:
        existing = by_date.get(s.date)
        if not existing or source_priority.get(s.source.value, 99) < source_priority.get(
            existing.source.value, 99
        ):
            by_date[s.date] = s

    return {
        "data": [
            {
                "date": s.date,
                "total_minutes": s.total_sleep_minutes,
                "deep_minutes": s.deep_sleep_minutes,
                "rem_minutes": s.rem_sleep_minutes,
                "light_minutes": s.light_sleep_minutes,
                "awake_minutes": s.awake_minutes,
                "efficiency": s.efficiency,
                "score": s.sleep_score,
                "avg_hr": s.avg_heart_rate,
                "avg_hrv": s.avg_hrv,
                "source": s.source.value,
            }
            for s in sorted(by_date.values(), key=lambda x: x.date)
        ]
    }


@router.get("/workouts/summary")
async def get_workout_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get workout summary and stats."""
    since = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())

    workouts = (
        db.query(Workout)
        .filter(Workout.start_time >= since)
        .order_by(Workout.start_time.desc())
        .all()
    )

    # Group by activity type
    by_type = {}
    for w in workouts:
        t = w.activity_type
        if t not in by_type:
            by_type[t] = {"count": 0, "total_minutes": 0, "total_calories": 0, "total_distance_km": 0}
        by_type[t]["count"] += 1
        by_type[t]["total_minutes"] += w.duration_minutes or 0
        by_type[t]["total_calories"] += w.calories or 0
        by_type[t]["total_distance_km"] += w.distance_km or 0

    return {
        "total_workouts": len(workouts),
        "total_minutes": sum(w.duration_minutes or 0 for w in workouts),
        "total_calories": sum(w.calories or 0 for w in workouts),
        "by_type": by_type,
        "recent": [
            {
                "type": w.activity_type,
                "date": w.start_time.isoformat() if w.start_time else None,
                "duration_minutes": w.duration_minutes,
                "calories": w.calories,
                "distance_km": w.distance_km,
                "avg_hr": w.avg_heart_rate,
                "source": w.source.value,
            }
            for w in workouts[:20]
        ],
    }
