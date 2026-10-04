from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.entities import Crop, CropRegion, CropVariety, Location

router = APIRouter(prefix="/api")


@router.get("/locations")
def list_locations(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Location).order_by(Location.region, Location.province)).all()
    return [
        {"id": row.id, "region": row.region, "province": row.province, "latitude": row.latitude, "longitude": row.longitude}
        for row in rows
    ]


def _crop_summary(crop: Crop) -> dict:
    return {
        "id": crop.id,
        "name": crop.name,
        "scientific_name": crop.scientific_name,
        "category": crop.category,
        "description": crop.description,
        "growing_days_min": crop.growing_days_min,
        "growing_days_max": crop.growing_days_max,
    }


@router.get("/crops")
def list_crops(db: Session = Depends(get_db)) -> list[dict]:
    return [_crop_summary(crop) for crop in db.scalars(select(Crop).order_by(Crop.name)).all()]


@router.get("/crops/{crop_id}")
def get_crop(crop_id: int, db: Session = Depends(get_db)) -> dict:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="crop not found")
    varieties = db.scalars(select(CropVariety).where(CropVariety.crop_id == crop.id)).all()
    regions = db.scalars(select(CropRegion).where(CropRegion.crop_id == crop.id)).all()
    return {
        **_crop_summary(crop),
        "optimal_temperature_min": crop.optimal_temperature_min,
        "optimal_temperature_max": crop.optimal_temperature_max,
        "optimal_rainfall_min": crop.optimal_rainfall_min,
        "optimal_rainfall_max": crop.optimal_rainfall_max,
        "water_requirement": crop.water_requirement,
        "soil_requirements": crop.soil_requirements,
        "suitable_months": crop.suitable_months,
        "varieties": [
            {"id": item.id, "name": item.name, "growing_days": item.growing_days, "yield_min": item.yield_min, "yield_max": item.yield_max, "yield_unit": item.yield_unit}
            for item in varieties
        ],
        "regions": [
            {"region": item.region, "province": item.province, "suitable": item.suitable, "historical_yield": item.historical_yield, "yield_unit": item.yield_unit}
            for item in regions
        ],
    }


@router.get("/crops/{crop_id}/requirements")
def crop_requirements(crop_id: int, db: Session = Depends(get_db)) -> dict:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="crop not found")
    return {
        "crop": crop.name,
        "temperature_c": {"min": crop.optimal_temperature_min, "max": crop.optimal_temperature_max},
        "rainfall_mm": {"min": crop.optimal_rainfall_min, "max": crop.optimal_rainfall_max},
        "growing_days": {"min": crop.growing_days_min, "max": crop.growing_days_max},
        "suitable_months": crop.suitable_months,
        "water_requirement": crop.water_requirement,
        "soil_requirements": crop.soil_requirements,
    }
