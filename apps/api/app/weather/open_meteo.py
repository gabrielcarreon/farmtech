from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.predictions.weather_score import DayWeather

logger = logging.getLogger(__name__)

# #region agent log
_DEBUG_LOG = Path(__file__).resolve().parents[4] / "debug-cc5a38.log"


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "cc5a38",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


# #endregion


def fetch_forecast(latitude: float, longitude: float, redis_client=None) -> dict[date, DayWeather]:
    settings = get_settings()
    cache_key = f"forecast:{latitude:.3f}:{longitude:.3f}"
    if redis_client is not None:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                # #region agent log
                _agent_log("D", "open_meteo.py:cache_hit", "forecast served from redis", {"cache_key": cache_key})
                # #endregion
                return _decode(json.loads(cached))
        except Exception:
            logger.info("forecast cache read failed", exc_info=True)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": 16,
        "timezone": "Asia/Manila",
    }
    try:
        response = httpx.get(settings.open_meteo_base_url, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        logger.info("forecast request failed", exc_info=True)
        return {}

    # #region agent log
    daily = payload.get("daily") or {}
    mins = daily.get("temperature_2m_min") or []
    maxs = daily.get("temperature_2m_max") or []
    rain = daily.get("precipitation_sum") or []
    times = daily.get("time") or []
    null_min = [i for i, v in enumerate(mins) if v is None]
    null_max = [i for i, v in enumerate(maxs) if v is None]
    null_rain = [i for i, v in enumerate(rain) if v is None]
    _agent_log(
        "A",
        "open_meteo.py:fetch_forecast",
        "open-meteo daily payload shape",
        {
            "lat": latitude,
            "lon": longitude,
            "len_time": len(times),
            "len_min": len(mins),
            "len_max": len(maxs),
            "len_rain": len(rain),
            "null_min_indexes": null_min,
            "null_max_indexes": null_max,
            "null_rain_indexes": null_rain,
            "trailing_days": [
                {
                    "index": i,
                    "date": times[i] if i < len(times) else None,
                    "min": mins[i] if i < len(mins) else "missing",
                    "max": maxs[i] if i < len(maxs) else "missing",
                    "rain": rain[i] if i < len(rain) else "missing",
                }
                for i in range(max(0, len(times) - 3), len(times))
            ],
        },
    )
    # #endregion

    parsed = _parse_open_meteo(payload)
    if redis_client is not None and parsed:
        try:
            redis_client.set(cache_key, json.dumps(_encode(parsed)), ex=settings.weather_cache_seconds)
        except Exception:
            logger.info("forecast cache write failed", exc_info=True)
    return parsed


def _parse_open_meteo(payload: dict) -> dict[date, DayWeather]:
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    mins = daily.get("temperature_2m_min") or []
    maxs = daily.get("temperature_2m_max") or []
    rain = daily.get("precipitation_sum") or []
    series: dict[date, DayWeather] = {}
    for index, raw_day in enumerate(times):
        temp_min = mins[index] if index < len(mins) else None
        temp_max = maxs[index] if index < len(maxs) else None
        rainfall = rain[index] if index < len(rain) else None
        if temp_min is None or temp_max is None:
            # #region agent log
            _agent_log(
                "A",
                "open_meteo.py:_parse_open_meteo",
                "skipping day with null temperature",
                {
                    "index": index,
                    "date": raw_day,
                    "temp_min": temp_min,
                    "temp_max": temp_max,
                    "rainfall": rainfall,
                    "is_trailing": index >= len(times) - 3,
                },
            )
            # #endregion
            continue
        series[date.fromisoformat(raw_day)] = DayWeather(
            day=date.fromisoformat(raw_day),
            temp_min=float(temp_min),
            temp_max=float(temp_max),
            rainfall=float(rainfall or 0),
            source="forecast",
        )
    # #region agent log
    _agent_log(
        "E",
        "open_meteo.py:_parse_open_meteo:done",
        "parsed forecast days",
        {"input_days": len(times), "parsed_days": len(series)},
    )
    # #endregion
    return series


def _encode(series: dict[date, DayWeather]) -> list[dict]:
    return [
        {
            "date": item.day.isoformat(),
            "temp_min": item.temp_min,
            "temp_max": item.temp_max,
            "rainfall": item.rainfall,
            "source": item.source,
        }
        for item in series.values()
    ]


def _decode(rows: list[dict]) -> dict[date, DayWeather]:
    series: dict[date, DayWeather] = {}
    for row in rows:
        day = date.fromisoformat(row["date"])
        series[day] = DayWeather(
            day=day,
            temp_min=row["temp_min"],
            temp_max=row["temp_max"],
            rainfall=row["rainfall"],
            source=row.get("source", "forecast"),
        )
    return series
