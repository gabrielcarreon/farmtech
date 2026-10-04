from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.redis import get_redis
from app.models.entities import Location, WeatherHistory
from app.weather.open_meteo import fetch_forecast

router = APIRouter(prefix="/api/weather")


@router.get("/forecast")
def forecast(
    latitude: float = Query(...),
    longitude: float = Query(...),
) -> dict:
    try:
        redis_client = get_redis()
    except Exception:
        redis_client = None
    series = fetch_forecast(latitude, longitude, redis_client)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "days": [
            {
                "date": item.day.isoformat(),
                "temperature_min": item.temp_min,
                "temperature_max": item.temp_max,
                "rainfall": item.rainfall,
                "source": item.source,
            }
            for item in sorted(series.values(), key=lambda item: item.day)
        ],
    }


@router.get("/history")
def history(
    province: str | None = None,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(WeatherHistory).order_by(WeatherHistory.date)
    if province:
        location = db.scalar(select(Location).where(Location.province.ilike(province)))
        if location is None:
            raise HTTPException(status_code=404, detail="location not found")
        stmt = stmt.where(WeatherHistory.location == location.province)
    if start:
        stmt = stmt.where(WeatherHistory.date >= start)
    if end:
        stmt = stmt.where(WeatherHistory.date <= end)
    rows = db.scalars(stmt.limit(400)).all()
    return {
        "days": [
            {
                "location": row.location,
                "date": row.date.isoformat(),
                "temperature_min": row.temperature_min,
                "temperature_max": row.temperature_max,
                "rainfall": row.rainfall,
                "humidity": row.humidity,
                "source": row.source,
            }
            for row in rows
        ]
    }
