from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import dashboard, ingest, insights, reports

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Health Dashboard API",
    description="Unified health data from Apple Health, Oura Ring, and Garmin",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(dashboard.router)
app.include_router(insights.router)
app.include_router(reports.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
