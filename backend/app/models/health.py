from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base

import enum


class Source(str, enum.Enum):
    APPLE_HEALTH = "apple_health"
    OURA = "oura"
    GARMIN = "garmin"
    MANUAL = "manual"


class MetricType(str, enum.Enum):
    HEART_RATE = "heart_rate"
    RESTING_HEART_RATE = "resting_heart_rate"
    HRV = "hrv"
    STEPS = "steps"
    CALORIES_ACTIVE = "calories_active"
    CALORIES_TOTAL = "calories_total"
    DISTANCE = "distance"
    FLOORS_CLIMBED = "floors_climbed"
    BLOOD_OXYGEN = "blood_oxygen"
    RESPIRATORY_RATE = "respiratory_rate"
    BODY_TEMPERATURE = "body_temperature"
    BODY_WEIGHT = "body_weight"
    BODY_FAT = "body_fat"
    BLOOD_PRESSURE_SYSTOLIC = "blood_pressure_systolic"
    BLOOD_PRESSURE_DIASTOLIC = "blood_pressure_diastolic"
    VO2_MAX = "vo2_max"
    STRESS = "stress"
    READINESS = "readiness"
    BODY_BATTERY = "body_battery"
    SLEEP_SCORE = "sleep_score"


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_type = Column(SAEnum(MetricType), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(50))
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(SAEnum(Source), nullable=False, index=True)
    source_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_metric_type_timestamp", "metric_type", "timestamp"),
        Index("ix_source_metric_timestamp", "source", "metric_type", "timestamp"),
    )


class SleepSession(Base):
    __tablename__ = "sleep_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)
    bedtime = Column(DateTime)
    wake_time = Column(DateTime)
    total_sleep_minutes = Column(Integer)
    deep_sleep_minutes = Column(Integer)
    rem_sleep_minutes = Column(Integer)
    light_sleep_minutes = Column(Integer)
    awake_minutes = Column(Integer)
    sleep_score = Column(Float)
    efficiency = Column(Float)
    avg_heart_rate = Column(Float)
    avg_hrv = Column(Float)
    avg_respiratory_rate = Column(Float)
    lowest_heart_rate = Column(Float)
    source = Column(SAEnum(Source), nullable=False, index=True)
    source_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    stages = relationship("SleepStage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_sleep_date_source", "date", "source"),)


class SleepStage(Base):
    __tablename__ = "sleep_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sleep_sessions.id"), nullable=False)
    stage = Column(String(20), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    session = relationship("SleepSession", back_populates="stages")


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_type = Column(String(100), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    duration_minutes = Column(Float)
    calories = Column(Float)
    distance_km = Column(Float)
    avg_heart_rate = Column(Float)
    max_heart_rate = Column(Float)
    avg_pace = Column(String(20))
    elevation_gain = Column(Float)
    training_effect_aerobic = Column(Float)
    training_effect_anaerobic = Column(Float)
    vo2_max = Column(Float)
    notes = Column(Text)
    source = Column(SAEnum(Source), nullable=False, index=True)
    source_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)
    steps = Column(Integer)
    calories_active = Column(Float)
    calories_total = Column(Float)
    distance_km = Column(Float)
    floors_climbed = Column(Integer)
    resting_heart_rate = Column(Float)
    avg_hrv = Column(Float)
    avg_stress = Column(Float)
    body_battery_high = Column(Integer)
    body_battery_low = Column(Integer)
    readiness_score = Column(Float)
    activity_score = Column(Float)
    sleep_score = Column(Float)
    spo2_avg = Column(Float)
    respiratory_rate = Column(Float)
    source = Column(SAEnum(Source), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_daily_date_source", "date", "source"),)


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(SAEnum(Source), nullable=False, unique=True)
    enabled = Column(Integer, default=0)
    last_sync = Column(DateTime)
    config = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
