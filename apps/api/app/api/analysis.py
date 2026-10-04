from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.entities import Analysis
from app.sentiment.client import AIClient
from app.services.analysis_service import AnalysisError, AnalysisService

router = APIRouter(prefix="/api/analysis")


class LocationIn(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    province: str | None = None
    region: str | None = None


class AnalysisIn(BaseModel):
    location: LocationIn
    farm_size_hectares: float = Field(gt=0, le=10000)
    planting_date: date
    horizon_months: int = Field(ge=1, le=18)
    available_capital: float = Field(ge=0)


@router.post("/crops")
async def create_analysis(body: AnalysisIn, db: Session = Depends(get_db)) -> dict:
    payload = body.model_dump(mode="json")
    service = AnalysisService(db, AIClient())
    try:
        result = service.run(payload)
    except AnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if result["ai"]["status"] == "ok":
        await _enqueue("refresh_market_sentiment")
        await _enqueue("embed_pending_chunks")
    return result


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    record = db.get(Analysis, analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return record.result


async def _enqueue(job_name: str) -> None:
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import get_settings

        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        await pool.enqueue_job(job_name)
        await pool.aclose()
    except Exception:
        return
