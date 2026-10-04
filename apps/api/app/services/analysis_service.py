from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    Analysis,
    ClimateNormal,
    Crop,
    CropCost,
    CropPrice,
    CropRegion,
    CropVariety,
    CropYield,
    Location,
    MarketSentiment,
    ScoringProfile,
)
from app.predictions.explain import build_explanation
from app.predictions.profit import adjust_yield_band, profit_scenarios
from app.predictions.risk import (
    confidence_from_data,
    data_risk,
    market_risk,
    overall_risk,
    price_volatility,
    production_risk,
    risk_label,
    weather_risk,
)
from app.predictions.weather_score import (
    MonthClimate,
    ScoringWeights,
    build_growing_period,
    day_is_extreme,
    development_stage,
    weather_suitability,
)
from app.rag.retrieve import search_chunks
from app.sentiment.client import AIClient, resolve_sentiment
from app.weather.open_meteo import fetch_forecast

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "These figures are data-driven scenarios with stated assumptions, not guarantees of yield, price, weather, or profit."
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


class AnalysisError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class AnalysisService:
    def __init__(self, db: Session, ai: AIClient | None = None, redis_client=None):
        self.db = db
        self.ai = ai or AIClient()
        self.redis = redis_client

    def run(self, payload: dict) -> dict:
        started = datetime.now(timezone.utc)
        location = self._resolve_location(payload["location"])
        profile = self.db.scalar(select(ScoringProfile).where(ScoringProfile.is_active.is_(True)))
        weights = ScoringWeights.from_mapping(profile.weights) if profile else ScoringWeights()
        scoring_version = profile.version if profile else "unversioned-default"
        crops = self._crops_for_region(location.region)
        if not crops:
            raise AnalysisError("No crops are recorded for this region")
        normals = self._normals(location.id)
        forecast = fetch_forecast(location.latitude, location.longitude, self.redis)
        ai_up = self.ai.is_healthy()
        model_info = self.ai.model_info() if ai_up else None
        queries = [f"rainfall temperature growing requirements for {crop.name}" for crop in crops]
        embeddings: list[list[float] | None] = [None] * len(crops)
        if ai_up:
            try:
                embedded = self.ai.embed(queries)
                vectors = embedded.get("embeddings") or []
                expected = get_settings().embedding_dimension
                for index, vector in enumerate(vectors):
                    if isinstance(vector, list) and len(vector) == expected:
                        embeddings[index] = vector
            except Exception:
                logger.info("query embedding skipped", exc_info=True)

        crop_results = []
        document_ids: list[int] = []
        price_ids: list[int] = []
        cost_ids: list[int] = []
        for crop, query, embedding in zip(crops, queries, embeddings):
            crop_result, refs = self._score_crop(
                crop=crop,
                location=location,
                payload=payload,
                weights=weights,
                normals=normals,
                forecast=forecast,
                ai_up=ai_up,
                query=query,
                query_embedding=embedding,
            )
            crop_results.append(crop_result)
            document_ids.extend(refs["documents"])
            price_ids.extend(refs["prices"])
            if refs["cost"] is not None:
                cost_ids.append(refs["cost"])

        settings = get_settings()
        result = {
            "disclaimer": DISCLAIMER,
            "location": {
                "region": location.region,
                "province": location.province,
                "latitude": location.latitude,
                "longitude": location.longitude,
            },
            "planting_date": payload["planting_date"],
            "horizon_months": payload["horizon_months"],
            "farm_size_hectares": payload["farm_size_hectares"],
            "available_capital": payload["available_capital"],
            "scoring_version": scoring_version,
            "model_versions": {
                "prediction": settings.prediction_model_version,
                "scoring": scoring_version,
                "sentiment": (model_info or {}).get("sentiment"),
                "embedding": (model_info or {}).get("embedding"),
                "llm": (model_info or {}).get("llm") or "template-v1",
            },
            "ai": {"status": "ok" if ai_up else "unavailable"},
            "freshness": {
                "weather_retrieved_at": started.isoformat(),
                "forecast_provider": "open-meteo",
            },
            "crops": crop_results,
        }
        record = Analysis(
            input_snapshot=payload,
            result=result,
            scoring_version=scoring_version,
            prediction_model_version=settings.prediction_model_version,
            sentiment_model_version=(model_info or {}).get("sentiment"),
            embedding_model_version=(model_info or {}).get("embedding"),
            llm_model_version="template-v1",
            source_ids={"documents": document_ids, "prices": price_ids, "costs": cost_ids},
        )
        self.db.add(record)
        self.db.flush()
        stored = {**result, "id": record.id}
        record.result = stored
        self.db.commit()
        logger.info("analysis %s generated in %.2fs", record.id, (datetime.now(timezone.utc) - started).total_seconds())
        return stored

    def _resolve_location(self, incoming: dict) -> Location:
        province = (incoming.get("province") or "").strip()
        if province:
            found = self.db.scalar(select(Location).where(Location.province.ilike(province)))
            if found is not None:
                return found
        latitude = incoming.get("latitude")
        longitude = incoming.get("longitude")
        locations = list(self.db.scalars(select(Location)))
        if latitude is None or longitude is None or not locations:
            raise AnalysisError("Provide a known province or a latitude and longitude")
        return min(locations, key=lambda item: haversine_km(latitude, longitude, item.latitude, item.longitude))

    def _crops_for_region(self, region: str) -> list[Crop]:
        crop_ids = list(
            self.db.scalars(select(CropRegion.crop_id).where(CropRegion.region == region).distinct())
        )
        if not crop_ids:
            return list(self.db.scalars(select(Crop).order_by(Crop.name)))
        return list(self.db.scalars(select(Crop).where(Crop.id.in_(crop_ids)).order_by(Crop.name)))

    def _normals(self, location_id: int) -> dict[int, MonthClimate]:
        rows = self.db.scalars(select(ClimateNormal).where(ClimateNormal.location_id == location_id)).all()
        return {
            row.month: MonthClimate(row.temperature_min, row.temperature_max, row.rainfall_mm)
            for row in rows
        }

    def _score_crop(self, *, crop: Crop, location: Location, payload: dict, weights: ScoringWeights, normals, forecast, ai_up: bool, query: str, query_embedding) -> tuple[dict, dict]:
        assumptions = [
            "Yield, price, and cost figures come from the stored agricultural tables for this region. The bundled dataset is a sample, not an official statistic.",
            "Profit stays a range. The expected scenario uses the midpoint of the adjusted yield band and the median price.",
            "Sentiment is a separate market signal. It is not turned into pesos.",
        ]
        variety = self.db.scalar(select(CropVariety).where(CropVariety.crop_id == crop.id).order_by(CropVariety.id))
        raw_days = variety.growing_days if variety else round((crop.growing_days_min + crop.growing_days_max) / 2)
        horizon_days = int(payload["horizon_months"]) * 30
        growing_days = min(raw_days, horizon_days)
        if growing_days < raw_days:
            assumptions.append(
                f"The {raw_days}-day variety window was clipped to the {payload['horizon_months']}-month planning horizon ({growing_days} days)."
            )
        planting = date.fromisoformat(payload["planting_date"]) if isinstance(payload["planting_date"], str) else payload["planting_date"]
        if not normals:
            raise AnalysisError(f"No climate normals are stored for {location.province}")
        series = build_growing_period(planting, growing_days, forecast, normals)
        region_row = self.db.scalar(
            select(CropRegion).where(
                CropRegion.crop_id == crop.id,
                CropRegion.region == location.region,
                CropRegion.province == location.province,
            )
        )
        suitable = True if region_row is None else region_row.suitable
        if not suitable:
            assumptions.append("Regional records mark this crop as weakly suited here, so weather suitability is reduced.")
        weather = weather_suitability(
            series,
            temp_min=crop.optimal_temperature_min,
            temp_max=crop.optimal_temperature_max,
            rain_min=crop.optimal_rainfall_min,
            rain_max=crop.optimal_rainfall_max,
            planting_month=planting.month,
            suitable_months=list(crop.suitable_months or []),
            weights=weights,
            regional_suitable=suitable,
        )
        yield_rows = list(
            self.db.scalars(
                select(CropYield).where(
                    CropYield.crop_id == crop.id,
                    CropYield.region == location.region,
                    CropYield.province == location.province,
                )
            )
        )
        if len(yield_rows) < 2:
            yield_rows = list(
                self.db.scalars(select(CropYield).where(CropYield.crop_id == crop.id, CropYield.region == location.region))
            )
        if len(yield_rows) >= 2:
            low = min(row.yield_value for row in yield_rows)
            high = max(row.yield_value for row in yield_rows)
            assumptions.append("The yield band is the minimum and maximum of stored regional yield records, then narrowed when weather suitability is low.")
        elif variety is not None:
            low, high = variety.yield_min, variety.yield_max
            assumptions.append("Fewer than two regional yield records were found, so the variety yield band is used.")
        else:
            low, high = 0.0, 0.0
            assumptions.append("No yield records were found. Profit cannot be estimated.")
        adjusted_low, adjusted_high = adjust_yield_band(low, high, weather["overall_score"] if high else 0)
        prices = list(
            self.db.scalars(
                select(CropPrice)
                .where(CropPrice.crop_id == crop.id, CropPrice.region == location.region)
                .order_by(CropPrice.date)
            )
        )
        if prices:
            values = [row.price for row in prices]
            price_min, price_max = min(values), max(values)
            ordered = sorted(values)
            mid_index = len(ordered) // 2
            price_mid = ordered[mid_index] if len(ordered) % 2 else (ordered[mid_index - 1] + ordered[mid_index]) / 2
            latest_price_date = max(row.date for row in prices)
            price_age = (date.today() - latest_price_date).days
        else:
            price_min = price_mid = price_max = 0
            latest_price_date = None
            price_age = None
            assumptions.append("No regional prices were found, so revenue is zero in this scenario.")
        cost = self.db.scalar(
            select(CropCost)
            .where(CropCost.crop_id == crop.id, CropCost.region == location.region)
            .order_by(CropCost.effective_date.desc())
        )
        cost_per_ha = cost.total_cost if cost else 0
        if cost is None:
            assumptions.append("No production cost row was found. Cost is treated as zero and data risk increases.")
        economics = profit_scenarios(
            adjusted_low,
            adjusted_high,
            price_min,
            price_mid,
            price_max,
            cost_per_ha,
            float(payload["farm_size_hectares"]),
            weights.conservative_cost_multiplier,
        )
        capital_constrained = economics["cost"]["expected"] > float(payload["available_capital"])
        if capital_constrained:
            assumptions.append("Estimated production cost exceeds available capital. The profit range is still shown.")
        volatility = price_volatility([row.price for row in prices]) if prices else None
        stored_row = self.db.scalar(
            select(MarketSentiment)
            .where(MarketSentiment.crop_id == crop.id, MarketSentiment.region == location.region)
            .order_by(MarketSentiment.date.desc())
        )
        stored = None
        if stored_row is not None:
            stored = {
                "sentiment_index": stored_row.sentiment_index,
                "as_of": stored_row.date.isoformat(),
                "confidence": stored_row.confidence,
                "article_count": stored_row.article_count,
            }
        sentiment = resolve_sentiment(None, stored)
        if ai_up and stored is not None:
            sentiment["status"] = "ready"
            sentiment["source"] = "stored"
        elif not ai_up:
            sentiment["status"] = "pending"
            assumptions.append(
                "The local AI service did not respond. Sentiment status is pending and the latest stored signal is shown when one exists."
            )
        favorability = None
        if sentiment["index"] is not None:
            unit = (float(sentiment["index"]) + 1) / 2
            vol_term = 0.5 if volatility is None else volatility
            favorability = round(0.6 * unit + 0.4 * (1 - vol_term), 4)
        try:
            evidence = search_chunks(
                self.db,
                query,
                crop=crop.name,
                region=location.region,
                embedding=query_embedding,
            )
        except Exception:
            logger.info("retrieval failed for %s", crop.name, exc_info=True)
            evidence = []
            assumptions.append("Document retrieval failed, so this result has no cited passages.")
        if not evidence:
            assumptions.append("No agricultural document chunk matched this crop and region.")
        forecast_share = weather["forecast_days"] / growing_days if growing_days else 0
        risks = {
            "weather": weather_risk(weather["extreme_weather_risk"], weather["temperature_score"], weather["rainfall_score"]),
            "market": market_risk(price_min, price_max, price_mid, sentiment["index"], volatility),
            "production": production_risk(low, high, crop.production_sensitivity),
            "data": data_risk(
                price_age_days=price_age,
                yield_observations=len(yield_rows),
                cost_present=cost is not None,
                forecast_share=forecast_share,
                evidence_count=len(evidence),
            ),
        }
        if not suitable:
            risks["production"] = min(100, risks["production"] + 15)
        risks["overall"] = overall_risk(risks["weather"], risks["market"], risks["production"], risks["data"])
        for key in ("weather", "market", "production", "data", "overall"):
            risks[f"{key}_label"] = risk_label(risks[key])
        market = {
            "price_range": {"min": round(price_min, 2), "median": round(price_mid, 2), "max": round(price_max, 2)},
            "unit": "PHP/kg",
            "sentiment": sentiment["index"],
            "sentiment_status": sentiment["status"],
            "sentiment_as_of": sentiment["as_of"],
            "volatility": None if volatility is None else round(volatility, 4),
            "favorability": favorability,
        }
        explanation = build_explanation(crop.name, weather, market, economics, risks, evidence)
        timeline = [
            {
                "date": item.day.isoformat(),
                "temp_min": round(item.temp_min, 2),
                "temp_max": round(item.temp_max, 2),
                "rainfall": round(item.rainfall, 2),
                "source": item.source,
                "extreme": day_is_extreme(item, weights),
                "stage": development_stage(index, len(series)),
            }
            for index, item in enumerate(series)
        ]
        result = {
            "crop": crop.name,
            "crop_id": crop.id,
            "scientific_name": crop.scientific_name,
            "location": {"region": location.region, "province": location.province},
            "planting_date": planting.isoformat(),
            "growing_period_days": growing_days,
            "weather": weather,
            "market": market,
            "profit": economics["profit"],
            "revenue": economics["revenue"],
            "cost": economics["cost"],
            "yield": economics["yield"],
            "risk": risks,
            "confidence": confidence_from_data(risks["data"], len(yield_rows), forecast_share),
            "capital_constrained": capital_constrained,
            "sentiment": sentiment,
            "timeline": timeline,
            "assumptions": assumptions,
            "evidence": evidence,
            "explanation": explanation,
            "sources": {
                "weather": "Open-Meteo daily forecast where dated coverage exists; monthly climate normals after that.",
                "prices_as_of": latest_price_date.isoformat() if latest_price_date else None,
                "costs_as_of": cost.effective_date.isoformat() if cost else None,
                "price_ids": [row.id for row in prices],
                "yield_ids": [row.id for row in yield_rows],
                "cost_id": cost.id if cost else None,
                "documents": evidence,
            },
            "freshness": {
                "forecast_days": weather["forecast_days"],
                "climatology_days": weather["climatology_days"],
                "prices_as_of": latest_price_date.isoformat() if latest_price_date else None,
                "costs_as_of": cost.effective_date.isoformat() if cost else None,
                "sentiment_as_of": sentiment["as_of"],
                "sentiment_status": sentiment["status"],
            },
        }
        return result, {
            "documents": [item["document_id"] for item in evidence],
            "prices": [row.id for row in prices],
            "cost": cost.id if cost else None,
        }

