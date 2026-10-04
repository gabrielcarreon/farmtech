from __future__ import annotations


def adjust_yield_band(low: float, high: float, suitability: float) -> tuple[float, float]:
    suitability = max(0.0, min(1.0, suitability))
    if high < low:
        low, high = high, low
    adjusted_high = low + (high - low) * suitability
    return low, adjusted_high


def _pesos(value: float) -> int:
    return int(round(value))


def profit_scenarios(
    yield_low_per_ha: float,
    yield_high_per_ha: float,
    price_min: float,
    price_mid: float,
    price_max: float,
    cost_per_ha: float,
    hectares: float,
    cost_multiplier: float = 1.15,
) -> dict:
    yield_low = yield_low_per_ha * hectares
    yield_high = yield_high_per_ha * hectares
    yield_mid = (yield_low + yield_high) / 2
    base_cost = cost_per_ha * hectares
    conservative_cost = base_cost * cost_multiplier
    conservative_revenue = yield_low * price_min
    expected_revenue = yield_mid * price_mid
    optimistic_revenue = yield_high * price_max
    return {
        "yield": {
            "min": round(yield_low, 2),
            "mid": round(yield_mid, 2),
            "max": round(yield_high, 2),
            "unit": "kg",
        },
        "revenue": {
            "conservative": _pesos(conservative_revenue),
            "expected": _pesos(expected_revenue),
            "optimistic": _pesos(optimistic_revenue),
            "currency": "PHP",
        },
        "cost": {
            "per_hectare": _pesos(cost_per_ha),
            "expected": _pesos(base_cost),
            "conservative": _pesos(conservative_cost),
            "currency": "PHP",
        },
        "profit": {
            "conservative": _pesos(conservative_revenue - conservative_cost),
            "expected": _pesos(expected_revenue - base_cost),
            "optimistic": _pesos(optimistic_revenue - base_cost),
            "currency": "PHP",
        },
    }
