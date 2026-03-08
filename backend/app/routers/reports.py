"""Report generation endpoints for downloading health summaries."""

import io
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
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

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/health-summary")
async def generate_health_summary(
    days: int = Query(30, ge=1, le=365),
    format: str = Query("json", regex="^(json|markdown)$"),
    db: Session = Depends(get_db),
):
    """Generate a comprehensive health summary report for Claude analysis."""
    today = date.today()
    since_date = today - timedelta(days=days)
    since_dt = datetime.combine(since_date, datetime.min.time())

    # --- Gather all data ---

    # Daily summaries
    summaries = (
        db.query(DailySummary)
        .filter(DailySummary.date >= since_date.isoformat())
        .order_by(DailySummary.date)
        .all()
    )

    # Merge by date
    daily = {}
    for s in summaries:
        if s.date not in daily:
            daily[s.date] = {}
        d = daily[s.date]
        for field in [
            "steps", "calories_active", "calories_total", "resting_heart_rate",
            "avg_hrv", "avg_stress", "readiness_score", "activity_score",
            "sleep_score", "spo2_avg", "respiratory_rate", "body_battery_high",
            "body_battery_low",
        ]:
            val = getattr(s, field, None)
            if val is not None:
                d[field] = val

    # Sleep
    sleep_sessions = (
        db.query(SleepSession)
        .filter(SleepSession.date >= since_date.isoformat())
        .order_by(SleepSession.date)
        .all()
    )
    sleep_by_date = {}
    for s in sleep_sessions:
        if s.date not in sleep_by_date:
            sleep_by_date[s.date] = s

    # Workouts
    workouts = (
        db.query(Workout)
        .filter(Workout.start_time >= since_dt)
        .order_by(Workout.start_time)
        .all()
    )

    # Key metric averages
    metric_avgs = {}
    for mt in [
        MetricType.RESTING_HEART_RATE, MetricType.HRV, MetricType.STEPS,
        MetricType.BLOOD_OXYGEN, MetricType.VO2_MAX, MetricType.BODY_WEIGHT,
    ]:
        result = (
            db.query(
                func.avg(HealthMetric.value),
                func.min(HealthMetric.value),
                func.max(HealthMetric.value),
                func.count(HealthMetric.id),
            )
            .filter(
                HealthMetric.metric_type == mt,
                HealthMetric.timestamp >= since_dt,
            )
            .first()
        )
        if result and result[3] > 0:
            metric_avgs[mt.value] = {
                "avg": round(result[0], 1),
                "min": round(result[1], 1),
                "max": round(result[2], 1),
                "samples": result[3],
            }

    report = {
        "report_generated": datetime.now().isoformat(),
        "period": f"{since_date.isoformat()} to {today.isoformat()}",
        "days": days,
        "metric_averages": metric_avgs,
        "daily_data": [
            {"date": d, **v}
            for d, v in sorted(daily.items())
        ],
        "sleep": [
            {
                "date": s.date,
                "total_hours": round(s.total_sleep_minutes / 60, 1) if s.total_sleep_minutes else None,
                "deep_hours": round(s.deep_sleep_minutes / 60, 1) if s.deep_sleep_minutes else None,
                "rem_hours": round(s.rem_sleep_minutes / 60, 1) if s.rem_sleep_minutes else None,
                "light_hours": round(s.light_sleep_minutes / 60, 1) if s.light_sleep_minutes else None,
                "awake_minutes": s.awake_minutes,
                "efficiency": s.efficiency,
                "score": s.sleep_score,
                "avg_hr": s.avg_heart_rate,
                "avg_hrv": s.avg_hrv,
            }
            for s in sleep_by_date.values()
        ],
        "workouts": [
            {
                "date": w.start_time.strftime("%Y-%m-%d") if w.start_time else None,
                "type": w.activity_type,
                "duration_minutes": w.duration_minutes,
                "calories": w.calories,
                "distance_km": w.distance_km,
                "avg_hr": w.avg_heart_rate,
                "max_hr": w.max_heart_rate,
                "vo2_max": w.vo2_max,
            }
            for w in workouts
        ],
        "workout_totals": {
            "count": len(workouts),
            "total_minutes": round(sum(w.duration_minutes or 0 for w in workouts), 1),
            "total_calories": round(sum(w.calories or 0 for w in workouts), 1),
        },
    }

    if format == "markdown":
        md = _report_to_markdown(report)
        return StreamingResponse(
            io.BytesIO(md.encode()),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=health_report_{today}.md"},
        )

    return report


def _report_to_markdown(report: dict) -> str:
    """Convert report dict to a markdown document optimized for Claude analysis."""
    lines = [
        f"# Health Report",
        f"**Period:** {report['period']}",
        f"**Generated:** {report['report_generated']}",
        "",
        "## Key Metric Averages",
        "",
    ]

    for metric, stats in report.get("metric_averages", {}).items():
        name = metric.replace("_", " ").title()
        lines.append(f"- **{name}**: avg={stats['avg']}, min={stats['min']}, max={stats['max']} ({stats['samples']} samples)")

    lines.extend(["", "## Sleep Summary", ""])
    for s in report.get("sleep", []):
        total = f"{s['total_hours']}h" if s.get("total_hours") else "N/A"
        deep = f"{s['deep_hours']}h" if s.get("deep_hours") else "?"
        rem = f"{s['rem_hours']}h" if s.get("rem_hours") else "?"
        lines.append(
            f"- **{s['date']}**: {total} total (deep={deep}, rem={rem})"
            + (f", score={s['score']}" if s.get("score") else "")
            + (f", HRV={s['avg_hrv']}" if s.get("avg_hrv") else "")
        )

    lines.extend(["", "## Workouts", ""])
    for w in report.get("workouts", []):
        dur = f"{w['duration_minutes']:.0f}min" if w.get("duration_minutes") else "?"
        lines.append(
            f"- **{w['date']}** {w['type']}: {dur}"
            + (f", {w['calories']:.0f}cal" if w.get("calories") else "")
            + (f", {w['distance_km']:.1f}km" if w.get("distance_km") else "")
            + (f", avg HR {w['avg_hr']:.0f}" if w.get("avg_hr") else "")
        )

    totals = report.get("workout_totals", {})
    lines.extend([
        "",
        f"**Workout Totals:** {totals.get('count', 0)} workouts, "
        f"{totals.get('total_minutes', 0):.0f} minutes, "
        f"{totals.get('total_calories', 0):.0f} calories",
    ])

    lines.extend(["", "## Daily Data", ""])
    lines.append("| Date | Steps | Cal Active | RHR | HRV | Stress | Readiness | Sleep Score |")
    lines.append("|------|-------|-----------|-----|-----|--------|-----------|-------------|")
    for d in report.get("daily_data", []):
        lines.append(
            f"| {d['date']} "
            f"| {d.get('steps', '-')} "
            f"| {d.get('calories_active', '-')} "
            f"| {d.get('resting_heart_rate', '-')} "
            f"| {d.get('avg_hrv', '-')} "
            f"| {d.get('avg_stress', '-')} "
            f"| {d.get('readiness_score', '-')} "
            f"| {d.get('sleep_score', '-')} |"
        )

    lines.extend([
        "",
        "---",
        "*Upload this report to Claude for personalized health insights and recommendations.*",
    ])

    return "\n".join(lines)
