from app.predictions.profit import adjust_yield_band, profit_scenarios


def test_profit_ranges_stay_separate():
    result = profit_scenarios(8000, 10000, 40, 47.5, 55, 180000, 1, 1.15)
    assert result["profit"]["conservative"] == 113000
    assert result["profit"]["expected"] == 247500
    assert result["profit"]["optimistic"] == 370000
    assert result["profit"]["conservative"] < result["profit"]["expected"] < result["profit"]["optimistic"]
    assert result["yield"]["min"] != result["yield"]["max"]


def test_poor_weather_shrinks_the_yield_band_toward_the_low_end():
    low, high = adjust_yield_band(8000, 10000, 0)
    assert (low, high) == (8000, 8000)
    low, high = adjust_yield_band(8000, 10000, 0.5)
    assert (low, high) == (8000, 9000)


def test_farm_size_scales_yield_and_cost():
    result = profit_scenarios(1000, 1000, 10, 10, 10, 1000, 2, 1)
    assert result["yield"]["min"] == 2000
    assert result["cost"]["expected"] == 2000
    assert result["profit"]["expected"] == 18000
