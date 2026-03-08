"""Apple Health data ingestion service.

Supports two modes:
1. XML export upload: User exports from iPhone and uploads the ZIP/XML file
2. Shortcuts API: Apple Shortcuts sends health data to our API endpoint periodically
"""

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.health import (
    DailySummary,
    HealthMetric,
    MetricType,
    SleepSession,
    Source,
    Workout,
)

# Mapping from Apple Health type identifiers to our metric types
APPLE_HEALTH_TYPE_MAP = {
    "HKQuantityTypeIdentifierHeartRate": MetricType.HEART_RATE,
    "HKQuantityTypeIdentifierRestingHeartRate": MetricType.RESTING_HEART_RATE,
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": MetricType.HRV,
    "HKQuantityTypeIdentifierStepCount": MetricType.STEPS,
    "HKQuantityTypeIdentifierActiveEnergyBurned": MetricType.CALORIES_ACTIVE,
    "HKQuantityTypeIdentifierBasalEnergyBurned": MetricType.CALORIES_TOTAL,
    "HKQuantityTypeIdentifierDistanceWalkingRunning": MetricType.DISTANCE,
    "HKQuantityTypeIdentifierFlightsClimbed": MetricType.FLOORS_CLIMBED,
    "HKQuantityTypeIdentifierOxygenSaturation": MetricType.BLOOD_OXYGEN,
    "HKQuantityTypeIdentifierRespiratoryRate": MetricType.RESPIRATORY_RATE,
    "HKQuantityTypeIdentifierBodyTemperature": MetricType.BODY_TEMPERATURE,
    "HKQuantityTypeIdentifierBodyMass": MetricType.BODY_WEIGHT,
    "HKQuantityTypeIdentifierBodyFatPercentage": MetricType.BODY_FAT,
    "HKQuantityTypeIdentifierBloodPressureSystolic": MetricType.BLOOD_PRESSURE_SYSTOLIC,
    "HKQuantityTypeIdentifierBloodPressureDiastolic": MetricType.BLOOD_PRESSURE_DIASTOLIC,
    "HKQuantityTypeIdentifierVO2Max": MetricType.VO2_MAX,
}

APPLE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"

APPLE_WORKOUT_TYPE_MAP = {
    "HKWorkoutActivityTypeRunning": "running",
    "HKWorkoutActivityTypeCycling": "cycling",
    "HKWorkoutActivityTypeSwimming": "swimming",
    "HKWorkoutActivityTypeWalking": "walking",
    "HKWorkoutActivityTypeHiking": "hiking",
    "HKWorkoutActivityTypeYoga": "yoga",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "strength_training",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "strength_training",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "hiit",
    "HKWorkoutActivityTypeElliptical": "elliptical",
    "HKWorkoutActivityTypeRowing": "rowing",
    "HKWorkoutActivityTypeCrossTraining": "cross_training",
}


def parse_apple_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, APPLE_DATE_FORMAT)


def process_xml_export(file: BinaryIO, db: Session) -> dict:
    """Process an Apple Health XML export file (ZIP or raw XML)."""
    content = file.read()

    # Check if it's a ZIP file
    if content[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml_files = [f for f in zf.namelist() if f.endswith(".xml")]
            if not xml_files:
                raise ValueError("No XML file found in ZIP archive")
            # Usually 'apple_health_export/export.xml'
            export_file = next(
                (f for f in xml_files if "export" in f.lower()), xml_files[0]
            )
            xml_content = zf.read(export_file)
    else:
        xml_content = content

    counts = {"metrics": 0, "workouts": 0, "sleep": 0}

    # Use iterparse to handle large files efficiently
    context = ET.iterparse(io.BytesIO(xml_content), events=("end",))

    batch_metrics = []
    batch_workouts = []
    batch_size = 1000

    for event, elem in context:
        if elem.tag == "Record":
            record_type = elem.get("type", "")
            if record_type in APPLE_HEALTH_TYPE_MAP:
                try:
                    metric = HealthMetric(
                        metric_type=APPLE_HEALTH_TYPE_MAP[record_type],
                        value=float(elem.get("value", 0)),
                        unit=elem.get("unit", ""),
                        timestamp=parse_apple_date(elem.get("startDate", "")),
                        source=Source.APPLE_HEALTH,
                        source_id=f"ah_{record_type}_{elem.get('startDate', '')}",
                    )
                    batch_metrics.append(metric)
                    counts["metrics"] += 1
                except (ValueError, TypeError):
                    pass

            if len(batch_metrics) >= batch_size:
                db.bulk_save_objects(batch_metrics)
                db.flush()
                batch_metrics = []

            elem.clear()

        elif elem.tag == "Workout":
            try:
                activity = elem.get("workoutActivityType", "")
                workout = Workout(
                    activity_type=APPLE_WORKOUT_TYPE_MAP.get(
                        activity, activity.replace("HKWorkoutActivityType", "").lower()
                    ),
                    start_time=parse_apple_date(elem.get("startDate", "")),
                    end_time=parse_apple_date(elem.get("endDate", "")),
                    duration_minutes=float(elem.get("duration", 0)),
                    calories=float(elem.get("totalEnergyBurned", 0))
                    if elem.get("totalEnergyBurned")
                    else None,
                    distance_km=float(elem.get("totalDistance", 0))
                    if elem.get("totalDistance")
                    else None,
                    source=Source.APPLE_HEALTH,
                    source_id=f"ah_workout_{elem.get('startDate', '')}",
                )
                batch_workouts.append(workout)
                counts["workouts"] += 1
            except (ValueError, TypeError):
                pass

            if len(batch_workouts) >= batch_size:
                db.bulk_save_objects(batch_workouts)
                db.flush()
                batch_workouts = []

            elem.clear()

    # Save remaining batches
    if batch_metrics:
        db.bulk_save_objects(batch_metrics)
    if batch_workouts:
        db.bulk_save_objects(batch_workouts)

    db.commit()
    return counts


def ingest_shortcuts_data(data: dict, db: Session) -> dict:
    """Ingest health data sent from Apple Shortcuts.

    Expected payload format:
    {
        "metrics": [
            {"type": "heart_rate", "value": 72, "unit": "bpm", "timestamp": "2024-01-01T12:00:00Z"},
            ...
        ],
        "sleep": {
            "bedtime": "2024-01-01T23:00:00Z",
            "wake_time": "2024-01-02T07:00:00Z",
            "deep_minutes": 90,
            "rem_minutes": 120,
            "light_minutes": 180,
            "awake_minutes": 15,
            "date": "2024-01-01"
        },
        "workouts": [
            {
                "type": "running",
                "start": "2024-01-01T08:00:00Z",
                "end": "2024-01-01T09:00:00Z",
                "calories": 450,
                "distance_km": 8.5,
                "avg_hr": 155,
                "max_hr": 178
            }
        ]
    }
    """
    counts = {"metrics": 0, "sleep": 0, "workouts": 0}

    # Process metrics
    for m in data.get("metrics", []):
        try:
            metric_type = MetricType(m["type"])
        except ValueError:
            continue

        metric = HealthMetric(
            metric_type=metric_type,
            value=float(m["value"]),
            unit=m.get("unit", ""),
            timestamp=datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")),
            source=Source.APPLE_HEALTH,
            source_id=f"shortcut_{m['type']}_{m['timestamp']}",
        )
        db.add(metric)
        counts["metrics"] += 1

    # Process sleep
    sleep_data = data.get("sleep")
    if sleep_data:
        session = SleepSession(
            date=sleep_data["date"],
            bedtime=datetime.fromisoformat(
                sleep_data["bedtime"].replace("Z", "+00:00")
            )
            if sleep_data.get("bedtime")
            else None,
            wake_time=datetime.fromisoformat(
                sleep_data["wake_time"].replace("Z", "+00:00")
            )
            if sleep_data.get("wake_time")
            else None,
            deep_sleep_minutes=sleep_data.get("deep_minutes"),
            rem_sleep_minutes=sleep_data.get("rem_minutes"),
            light_sleep_minutes=sleep_data.get("light_minutes"),
            awake_minutes=sleep_data.get("awake_minutes"),
            total_sleep_minutes=sum(
                filter(
                    None,
                    [
                        sleep_data.get("deep_minutes"),
                        sleep_data.get("rem_minutes"),
                        sleep_data.get("light_minutes"),
                    ],
                )
            ),
            source=Source.APPLE_HEALTH,
            source_id=f"shortcut_sleep_{sleep_data['date']}",
        )
        db.add(session)
        counts["sleep"] += 1

    # Process workouts
    for w in data.get("workouts", []):
        start = datetime.fromisoformat(w["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(w["end"].replace("Z", "+00:00"))
        workout = Workout(
            activity_type=w.get("type", "unknown"),
            start_time=start,
            end_time=end,
            duration_minutes=(end - start).total_seconds() / 60,
            calories=w.get("calories"),
            distance_km=w.get("distance_km"),
            avg_heart_rate=w.get("avg_hr"),
            max_heart_rate=w.get("max_hr"),
            source=Source.APPLE_HEALTH,
            source_id=f"shortcut_workout_{w['start']}",
        )
        db.add(workout)
        counts["workouts"] += 1

    db.commit()
    return counts
