"""Data ingestion endpoints for all health sources."""

from datetime import date

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.apple_health import ingest_shortcuts_data, process_xml_export
from app.services.garmin import sync_garmin_data, sync_garmin_full_history
from app.services.oura import sync_oura_data, sync_oura_full_history

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


# --- Apple Health ---


@router.post("/apple-health/upload")
async def upload_apple_health_export(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload an Apple Health XML export (ZIP or raw XML)."""
    if not file.filename.endswith((".xml", ".zip")):
        raise HTTPException(400, "File must be .xml or .zip")

    counts = process_xml_export(file.file, db)
    return {"status": "ok", "imported": counts}


class ShortcutsPayload(BaseModel):
    metrics: list[dict] = []
    sleep: dict | None = None
    workouts: list[dict] = []


@router.post("/apple-health/shortcuts")
async def apple_health_shortcuts(
    payload: ShortcutsPayload,
    x_api_key: str = Header(...),
    db: Session = Depends(get_db),
):
    """Receive health data from Apple Shortcuts automation."""
    if x_api_key != settings.apple_health_api_key:
        raise HTTPException(401, "Invalid API key")

    counts = ingest_shortcuts_data(payload.model_dump(), db)
    return {"status": "ok", "imported": counts}


# --- Oura Ring ---


class SyncRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    full_history: bool = False


@router.post("/oura/sync")
async def sync_oura(
    req: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
):
    """Sync data from Oura Ring API."""
    if req.full_history:
        counts = await sync_oura_full_history(db)
    else:
        counts = await sync_oura_data(db, req.start_date, req.end_date)
    return {"status": "ok", "synced": counts}


# --- Garmin ---


@router.post("/garmin/sync")
async def sync_garmin(
    req: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
):
    """Sync data from Garmin Connect."""
    if req.full_history:
        counts = sync_garmin_full_history(db)
    else:
        counts = sync_garmin_data(db, req.start_date, req.end_date)
    return {"status": "ok", "synced": counts}
