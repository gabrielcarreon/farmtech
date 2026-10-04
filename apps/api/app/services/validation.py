from __future__ import annotations

from datetime import date, datetime


PRICE_UNITS = {"php/kg", "php/ton"}
YIELD_UNITS = {"kg/ha", "t/ha", "tons/ha"}
TEMP_MIN = -5
TEMP_MAX = 55


class RowError(Exception):
    def __init__(self, row: int, message: str):
        super().__init__(message)
        self.row = row
        self.message = message


def _required(row: dict, field: str, index: int) -> str:
    value = row.get(field)
    if value is None or str(value).strip() == "":
        raise RowError(index, f"{field} is required")
    return str(value).strip()


def _number(row: dict, field: str, index: int) -> float:
    raw = _required(row, field, index)
    try:
        return float(raw)
    except ValueError as exc:
        raise RowError(index, f"{field} must be numeric") from exc


def _parse_date(raw: str, index: int, field: str = "date") -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise RowError(index, f"{field} must be YYYY-MM-DD") from exc


def _reject_future(value: date, index: int, today: date, field: str = "date") -> None:
    if value > today:
        raise RowError(index, f"{field} cannot be in the future for a historical record")


def normalize_price_unit(unit: str, index: int) -> str:
    cleaned = unit.strip().lower().replace("₱", "php").replace(" ", "")
    aliases = {"php/kg": "PHP/kg", "php/ton": "PHP/ton", "₱/kg": "PHP/kg"}
    if cleaned not in aliases and unit.strip() not in {"PHP/kg", "PHP/ton"}:
        raise RowError(index, "price unit must be PHP/kg or PHP/ton")
    return aliases.get(cleaned, unit.strip())


def normalize_yield(value: float, unit: str, index: int) -> tuple[float, str]:
    cleaned = unit.strip().lower().replace(" ", "")
    if cleaned in {"kg/ha"}:
        return value, "kg/ha"
    if cleaned in {"t/ha", "tons/ha", "ton/ha"}:
        return value * 1000, "kg/ha"
    raise RowError(index, "yield unit must be kg/ha or t/ha")


def validate_price_row(row: dict, index: int, today: date | None = None) -> dict:
    today = today or date.today()
    price = _number(row, "price", index)
    if price < 0:
        raise RowError(index, "price must be >= 0")
    priced_on = _parse_date(_required(row, "date", index), index)
    _reject_future(priced_on, index, today)
    return {
        "crop": _required(row, "crop", index),
        "market": _required(row, "market", index),
        "region": _required(row, "region", index),
        "price": price if normalize_price_unit(_required(row, "unit", index), index) == "PHP/kg" else price / 1000,
        "unit": "PHP/kg",
        "date": priced_on,
        "source": _required(row, "source", index),
    }


def validate_yield_row(row: dict, index: int, today: date | None = None) -> dict:
    today = today or date.today()
    value = _number(row, "yield", index)
    if value < 0:
        raise RowError(index, "yield must be >= 0")
    recorded = _parse_date(_required(row, "date", index), index)
    _reject_future(recorded, index, today)
    normalized, unit = normalize_yield(value, _required(row, "unit", index), index)
    return {
        "crop": _required(row, "crop", index),
        "region": _required(row, "region", index),
        "province": (row.get("province") or "").strip() or None,
        "yield_value": normalized,
        "yield_unit": unit,
        "date": recorded,
        "source": _required(row, "source", index),
    }


def validate_weather_row(row: dict, index: int, today: date | None = None) -> dict:
    today = today or date.today()
    observed = _parse_date(_required(row, "date", index), index)
    _reject_future(observed, index, today)
    rainfall = _number(row, "rainfall", index)
    if rainfall < 0:
        raise RowError(index, "rainfall must be >= 0")
    temp_min = _number(row, "temperature_min", index)
    temp_max = _number(row, "temperature_max", index)
    if not (TEMP_MIN <= temp_min <= TEMP_MAX and TEMP_MIN <= temp_max <= TEMP_MAX):
        raise RowError(index, "temperature is outside the plausible range")
    if temp_min > temp_max:
        raise RowError(index, "temperature_min cannot exceed temperature_max")
    return {
        "location": _required(row, "location", index),
        "latitude": _number(row, "latitude", index),
        "longitude": _number(row, "longitude", index),
        "date": observed,
        "temperature_min": temp_min,
        "temperature_max": temp_max,
        "rainfall": rainfall,
        "source": _required(row, "source", index),
    }
