from datetime import date

from app.predictions.weather_score import (
    DayWeather,
    MonthClimate,
    ScoringWeights,
    build_growing_period,
    weather_suitability,
)


def _day(day: date, temp_min: float, temp_max: float, rainfall: float, source: str = "forecast") -> DayWeather:
    return DayWeather(day, temp_min, temp_max, rainfall, source)


def test_growing_period_uses_forecast_then_climate_normals():
    start = date(2026, 10, 15)
    forecast = {
        start: _day(start, 22, 31, 4),
    }
    normals = {10: MonthClimate(21, 32, 170)}
    series = build_growing_period(start, 3, forecast, normals)
    assert series[0].source == "forecast"
    assert series[0].rainfall == 4
    assert series[1].source == "climatology"
    assert series[2].source == "climatology"
    assert abs(series[1].rainfall - (170 / 31)) < 0.001


def test_suitability_is_high_when_every_day_is_inside_the_documented_range():
    start = date(2026, 10, 15)
    days = [_day(start.replace(day=15 + offset), 20, 28, 12) for offset in range(4)]
    result = weather_suitability(
        days,
        temp_min=18,
        temp_max=29,
        rain_min=40,
        rain_max=60,
        planting_month=10,
        suitable_months=[10, 11, 12],
        weights=ScoringWeights(),
    )
    assert result["temperature_score"] == 1
    assert result["rainfall_score"] == 1
    assert result["season_score"] == 1
    assert result["extreme_weather_risk"] == 0
    assert result["overall_score"] == 1


def test_extreme_day_lowers_suitability_and_custom_weights_are_applied():
    start = date(2026, 10, 15)
    days = [
        _day(start, 20, 40, 1),
        _day(start.replace(day=16), 20, 28, 1),
        _day(start.replace(day=17), 20, 28, 1),
        _day(start.replace(day=18), 20, 28, 1),
    ]
    default = weather_suitability(
        days,
        temp_min=18,
        temp_max=29,
        rain_min=0,
        rain_max=10,
        planting_month=10,
        suitable_months=[10],
        weights=ScoringWeights(),
    )
    assert default["extreme_weather_risk"] == 0.25
    assert default["overall_score"] < 1
    temperature_only = weather_suitability(
        days,
        temp_min=18,
        temp_max=29,
        rain_min=0,
        rain_max=10,
        planting_month=10,
        suitable_months=[10],
        weights=ScoringWeights(temperature=1, rainfall=0, season=0, extreme=0),
    )
    assert temperature_only["overall_score"] == temperature_only["temperature_score"]
