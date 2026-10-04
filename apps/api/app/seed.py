from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.market.aggregate import aggregate_sentiment
from app.models.entities import (
    ClimateNormal,
    Crop,
    CropCost,
    CropPrice,
    CropRegion,
    CropVariety,
    CropYield,
    Document,
    DocumentChunk,
    Location,
    MarketArticle,
    MarketSentiment,
    ScoringProfile,
    WeatherHistory,
)
from app.rag.chunking import chunk_text


def seed_dir() -> Path:
    override = os.environ.get("SEED_DATA_DIR")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "seed"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("seed data directory not found")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_guide(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text.strip()
    _, header, body = text.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def seed() -> None:
    root = seed_dir()
    session = SessionLocal()
    try:
        if session.scalar(select(func.count(Crop.id))) >= 5:
            return
        _seed(session, root)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed(session, root: Path) -> None:
    locations = {}
    for row in _load(root / "locations.json"):
        location = Location(**row)
        session.add(location)
        session.flush()
        locations[row["province"]] = location

    climate = _load(root / "climate.json")
    for province, months in climate.items():
        location = locations[province]
        for index in range(12):
            session.add(
                ClimateNormal(
                    location_id=location.id,
                    month=index + 1,
                    temperature_min=months["temperature_min"][index],
                    temperature_max=months["temperature_max"][index],
                    rainfall_mm=months["rainfall_mm"][index],
                    humidity=months["humidity"][index],
                )
            )

    yields = _load(root / "yields.json")
    unsuitable = {(item["crop"], item["province"]) for item in yields["unsuitable"]}
    crops = {}
    for row in _load(root / "crops.json"):
        variety = row.pop("variety")
        crop = Crop(**row)
        session.add(crop)
        session.flush()
        crops[crop.name] = crop
        session.add(
            CropVariety(
                crop_id=crop.id,
                name=variety["name"],
                description=variety["description"],
                growing_days=variety["growing_days"],
                yield_min=variety["yield_min"],
                yield_max=variety["yield_max"],
                yield_unit="kg/ha",
                temperature_requirements={"min": crop.optimal_temperature_min, "max": crop.optimal_temperature_max, "unit": "C"},
                rainfall_requirements={"min": crop.optimal_rainfall_min, "max": crop.optimal_rainfall_max, "unit": "mm"},
            )
        )
        for province, location in locations.items():
            series = yields["yields_kg_ha"][crop.name][province]
            session.add(
                CropRegion(
                    crop_id=crop.id,
                    region=location.region,
                    province=province,
                    suitable=(crop.name, province) not in unsuitable,
                    historical_yield=sum(series) / len(series),
                    yield_unit="kg/ha",
                )
            )

    costs = _load(root / "costs.json")
    for crop_name, by_region in costs.items():
        for region, total in by_region.items():
            session.add(
                CropCost(
                    crop_id=crops[crop_name].id,
                    region=region,
                    province=None,
                    seed_cost=round(total * 0.18, 2),
                    fertilizer_cost=round(total * 0.24, 2),
                    labor_cost=round(total * 0.32, 2),
                    pesticide_cost=round(total * 0.10, 2),
                    irrigation_cost=round(total * 0.08, 2),
                    equipment_cost=round(total * 0.05, 2),
                    other_cost=round(total * 0.03, 2),
                    total_cost=total,
                    effective_date=date(2026, 3, 1),
                    currency="PHP",
                )
            )

    prices = _load(root / "prices.json")
    for crop_name, by_region in prices["series"].items():
        for region, series in by_region.items():
            for recorded, value in zip(prices["dates"], series):
                session.add(
                    CropPrice(
                        crop_id=crops[crop_name].id,
                        market=prices["markets"][region],
                        region=region,
                        price=value,
                        unit="PHP/kg",
                        date=date.fromisoformat(recorded),
                        source=prices["source"],
                    )
                )

    for crop_name, by_province in yields["yields_kg_ha"].items():
        for province, series in by_province.items():
            for year, value in zip(yields["years"], series):
                session.add(
                    CropYield(
                        crop_id=crops[crop_name].id,
                        region=locations[province].region,
                        province=province,
                        yield_value=value,
                        yield_unit="kg/ha",
                        date=date(year, 9, 1),
                        source=yields["source"],
                    )
                )

    today = date.today()
    for province, location in locations.items():
        month_climate = climate[province]
        for offset in range(1, 22):
            observed = today - timedelta(days=offset)
            month_index = observed.month - 1
            dim = 30
            session.add(
                WeatherHistory(
                    location=province,
                    latitude=location.latitude,
                    longitude=location.longitude,
                    date=observed,
                    temperature_min=month_climate["temperature_min"][month_index],
                    temperature_max=month_climate["temperature_max"][month_index],
                    rainfall=round(month_climate["rainfall_mm"][month_index] / dim, 2),
                    humidity=month_climate["humidity"][month_index],
                    weather_condition="climate-normal",
                    source="monthly-climate-normal-demo",
                )
            )

    for path in sorted((root / "guides").glob("*.md")):
        meta, body = _parse_guide(path.read_text(encoding="utf-8"))
        document = Document(
            title=meta["title"],
            source=meta.get("source"),
            document_type=meta.get("document_type", "production_guide"),
            publication_date=date(int(meta.get("year", "2024")), 6, 1),
            region=meta.get("region"),
            province=meta.get("province"),
            metadata_json={
                "crop": meta.get("crop"),
                "year": int(meta["year"]) if meta.get("year") else None,
                "data_quality": "sample",
            },
        )
        session.add(document)
        session.flush()
        for index, piece in enumerate(chunk_text(body)):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=piece["content"],
                    metadata_json={
                        "crop": meta.get("crop"),
                        "region": meta.get("region"),
                        "province": meta.get("province"),
                        "section": piece.get("section"),
                        "embedding_status": "pending",
                    },
                )
            )

    grouped: dict[tuple[int, str], list] = {}
    sentiment_dates: dict[tuple[int, str], date] = {}
    for article in _load(root / "articles.json"):
        crop = crops[article["crop"]]
        published = date.fromisoformat(article["published_at"])
        session.add(
            MarketArticle(
                crop_id=crop.id,
                region=article["region"],
                title=article["title"],
                content=article["content"],
                source=article["source"],
                published_at=published,
                sentiment=article["sentiment"],
                status="seeded",
            )
        )
        key = (crop.id, article["region"])
        grouped.setdefault(key, []).append(article["sentiment"])
        sentiment_dates[key] = max(sentiment_dates.get(key, published), published)
    for key, scores in grouped.items():
        summary = aggregate_sentiment(scores)
        if summary is None:
            continue
        crop_id, region = key
        session.add(MarketSentiment(crop_id=crop_id, region=region, date=sentiment_dates[key], **summary))

    profile = _load(root / "scoring.json")
    session.add(ScoringProfile(**profile))


if __name__ == "__main__":
    seed()
