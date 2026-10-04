from __future__ import annotations

import calendar
from dataclasses import dataclass, fields
from datetime import date, timedelta


@dataclass(frozen=True)
class ScoringWeights:
    temperature: float = 0.35
    rainfall: float = 0.35
    season: float = 0.15
    extreme: float = 0.15
    conservative_cost_multiplier: float = 1.15
    extreme_temp_high_c: float = 38.0
    extreme_temp_low_c: float = 10.0
    extreme_daily_rain_mm: float = 80.0

    @classmethod
    def from_mapping(cls, data: dict) -> ScoringWeights:
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass(frozen=True)
class DayWeather:
    day: date
    temp_min: float
    temp_max: float
    rainfall: float
    source: str

    @property
    def temp_mean(self) -> float:
        return (self.temp_min + self.temp_max) / 2


@dataclass(frozen=True)
class MonthClimate:
    temperature_min: float
    temperature_max: float
    rainfall_mm: float


def build_growing_period(
    start: date,
    days: int,
    forecast: dict[date, DayWeather],
    normals: dict[int, MonthClimate],
) -> list[DayWeather]:
    if days < 1:
        raise ValueError("growing period must cover at least one day")
    series: list[DayWeather] = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        observed = forecast.get(current)
        if observed is not None:
            series.append(
                DayWeather(
                    day=current,
                    temp_min=observed.temp_min,
                    temp_max=observed.temp_max,
                    rainfall=observed.rainfall,
                    source="forecast",
                )
            )
            continue
        climate = normals[current.month]
        month_days = calendar.monthrange(current.year, current.month)[1]
        series.append(
            DayWeather(
                day=current,
                temp_min=climate.temperature_min,
                temp_max=climate.temperature_max,
                rainfall=climate.rainfall_mm / month_days,
                source="climatology",
            )
        )
    return series


def development_stage(index: int, total: int) -> str:
    fraction = index / max(total - 1, 1)
    if fraction < 0.25:
        return "establishment"
    if fraction < 0.55:
        return "vegetative"
    if fraction < 0.85:
        return "reproductive"
    return "maturation"


def _band_score(value: float, low: float, high: float) -> float:
    if low <= value <= high:
        return 1.0
    width = max(high - low, 1.0)
    if value < low:
        return max(0.0, 1.0 - (low - value) / width)
    return max(0.0, 1.0 - (value - high) / width)


def temperature_score(days: list[DayWeather], temp_min: float, temp_max: float) -> float:
    if not days:
        return 0.0
    total = sum(_band_score(item.temp_mean, temp_min, temp_max) for item in days)
    return total / len(days)


def rainfall_score(days: list[DayWeather], rain_min: float, rain_max: float) -> float:
    return _band_score(sum(item.rainfall for item in days), rain_min, rain_max)


def season_score(month: int, suitable_months: list[int]) -> float:
    if not suitable_months:
        return 0.5
    if month in suitable_months:
        return 1.0

    def distance(left: int, right: int) -> int:
        gap = abs(left - right)
        return min(gap, 12 - gap)

    nearest = min(distance(month, suitable) for suitable in suitable_months)
    return max(0.0, 1.0 - nearest / 3)


def day_is_extreme(day: DayWeather, weights: ScoringWeights) -> bool:
    return (
        day.temp_max >= weights.extreme_temp_high_c
        or day.temp_min <= weights.extreme_temp_low_c
        or day.rainfall >= weights.extreme_daily_rain_mm
    )


def extreme_risk(days: list[DayWeather], weights: ScoringWeights) -> float:
    if not days:
        return 0.0
    flagged = sum(1 for item in days if day_is_extreme(item, weights))
    return flagged / len(days)


def weather_suitability(
    days: list[DayWeather],
    *,
    temp_min: float,
    temp_max: float,
    rain_min: float,
    rain_max: float,
    planting_month: int,
    suitable_months: list[int],
    weights: ScoringWeights,
    regional_suitable: bool = True,
) -> dict:
    temp = temperature_score(days, temp_min, temp_max)
    rain = rainfall_score(days, rain_min, rain_max)
    season = season_score(planting_month, suitable_months)
    extreme = extreme_risk(days, weights)
    overall = (
        weights.temperature * temp
        + weights.rainfall * rain
        + weights.season * season
        + weights.extreme * (1.0 - extreme)
    )
    if not regional_suitable:
        overall *= 0.75
    forecast_days = sum(1 for item in days if item.source == "forecast")
    return {
        "temperature_score": round(temp, 4),
        "rainfall_score": round(rain, 4),
        "season_score": round(season, 4),
        "extreme_weather_risk": round(extreme, 4),
        "overall_score": round(max(0.0, min(1.0, overall)), 4),
        "forecast_days": forecast_days,
        "climatology_days": len(days) - forecast_days,
        "regional_suitable": regional_suitable,
    }
