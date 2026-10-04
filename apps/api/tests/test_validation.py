from datetime import date

import pytest

from app.services.validation import RowError, validate_price_row, validate_weather_row, validate_yield_row


def test_negative_price_is_rejected():
    with pytest.raises(RowError, match="price"):
        validate_price_row(
            {"crop": "Tomato", "market": "A", "region": "Central Luzon", "price": "-1", "unit": "PHP/kg", "date": "2026-09-01", "source": "sample"},
            1,
            today=date(2026, 9, 30),
        )


def test_future_historical_date_is_rejected():
    with pytest.raises(RowError, match="future"):
        validate_yield_row(
            {"crop": "Rice", "region": "Ilocos", "province": "Pangasinan", "yield": "4", "unit": "t/ha", "date": "2027-01-01", "source": "sample"},
            2,
            today=date(2026, 9, 30),
        )


def test_unknown_unit_and_implausible_temperature_are_rejected():
    with pytest.raises(RowError, match="unit"):
        validate_price_row(
            {"crop": "Tomato", "market": "A", "region": "Central Luzon", "price": "10", "unit": "bushel", "date": "2026-09-01", "source": "sample"},
            3,
            today=date(2026, 9, 30),
        )
    with pytest.raises(RowError, match="temperature"):
        validate_weather_row(
            {
                "location": "Nueva Ecija",
                "latitude": "15.4",
                "longitude": "120.5",
                "date": "2026-09-01",
                "temperature_min": "10",
                "temperature_max": "80",
                "rainfall": "1",
                "source": "sample",
            },
            4,
            today=date(2026, 9, 30),
        )


def test_tons_are_normalized_to_kilograms():
    row = validate_yield_row(
        {"crop": "Rice", "region": "Ilocos", "province": "Pangasinan", "yield": "4.5", "unit": "t/ha", "date": "2026-09-01", "source": "sample"},
        1,
        today=date(2026, 9, 30),
    )
    assert row["yield_value"] == 4500
    assert row["yield_unit"] == "kg/ha"
