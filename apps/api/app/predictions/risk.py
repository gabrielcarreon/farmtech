from __future__ import annotations

import math


def clamp_score(value: float) -> int:
    return max(0, min(100, int(value + 0.5)))


def risk_label(score: int) -> str:
    bounded = max(0, min(100, int(score)))
    if bounded <= 20:
        return "Very Low"
    if bounded <= 40:
        return "Low"
    if bounded <= 60:
        return "Moderate"
    if bounded <= 80:
        return "High"
    return "Very High"


def weather_risk(extreme_risk_value: float, temperature_score: float, rainfall_score: float) -> int:
    raw = 0.6 * extreme_risk_value + 0.2 * (1 - temperature_score) + 0.2 * (1 - rainfall_score)
    return clamp_score(raw * 100)


def market_risk(price_min: float, price_max: float, price_mid: float, sentiment_index: float | None, sentiment_volatility: float | None) -> int:
    if price_mid <= 0:
        dispersion = 1.0
    else:
        dispersion = min(1.0, max(0.0, (price_max - price_min) / price_mid))
    if sentiment_index is None:
        sentiment_component = 0.5
    else:
        negativity = 1 - (max(-1.0, min(1.0, sentiment_index)) + 1) / 2
        volatility = 0.5 if sentiment_volatility is None else max(0.0, min(1.0, sentiment_volatility))
        sentiment_component = 0.5 * negativity + 0.5 * volatility
    return clamp_score((0.65 * dispersion + 0.35 * sentiment_component) * 100)


def production_risk(yield_min: float, yield_max: float, sensitivity: float) -> int:
    midpoint = (yield_min + yield_max) / 2
    if midpoint <= 0:
        spread = 1.0
    else:
        spread = min(1.0, max(0.0, (yield_max - yield_min) / midpoint))
    raw = 0.6 * spread + 0.4 * max(0.0, min(1.0, sensitivity))
    return clamp_score(raw * 100)


def data_risk(
    *,
    price_age_days: int | None,
    yield_observations: int,
    cost_present: bool,
    forecast_share: float,
    evidence_count: int,
) -> int:
    freshness = 0.6 if price_age_days is None else min(1.0, max(0.0, price_age_days / 365))
    observation_penalty = 1 - min(1.0, yield_observations / 8)
    forecast_penalty = 1 - max(0.0, min(1.0, forecast_share))
    evidence_penalty = 0.0 if evidence_count else 0.35
    cost_penalty = 0.0 if cost_present else 0.45
    raw = (
        0.30 * freshness
        + 0.25 * observation_penalty
        + 0.25 * forecast_penalty
        + 0.10 * evidence_penalty
        + 0.10 * cost_penalty
    )
    return clamp_score(raw * 100)


def overall_risk(weather: int, market: int, production: int, data: int) -> int:
    return clamp_score((weather + market + production + data) / 4)


def confidence_from_data(data_score: int, yield_observations: int, forecast_share: float) -> float:
    observation_boost = min(1.0, yield_observations / 8)
    raw = 1 - (data_score / 100) * 0.65 + 0.05 * observation_boost + 0.05 * forecast_share
    return round(max(0.15, min(0.95, raw)), 2)


def price_volatility(prices: list[float]) -> float | None:
    if len(prices) < 2:
        return None
    mean = sum(prices) / len(prices)
    if mean <= 0:
        return None
    variance = sum((price - mean) ** 2 for price in prices) / len(prices)
    return min(1.0, math.sqrt(variance) / mean)
