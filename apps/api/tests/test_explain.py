from app.predictions.explain import build_explanation
from app.sentiment.client import resolve_sentiment


def test_offline_sentiment_stays_pending_and_keeps_the_stored_signal():
    resolved = resolve_sentiment(None, {"sentiment_index": 0.42, "as_of": "2026-09-28", "confidence": 0.7, "article_count": 4})
    assert resolved["status"] == "pending"
    assert resolved["source"] == "stored"
    assert resolved["index"] == 0.42


def test_missing_sentiment_is_pending_without_a_fabricated_index():
    resolved = resolve_sentiment(None, None)
    assert resolved["status"] == "pending"
    assert resolved["index"] is None


def test_explanation_repeats_engine_numbers_and_does_not_invent_one():
    text = build_explanation(
        "Tomato",
        {"temperature_score": 0.86, "rainfall_score": 0.79, "extreme_weather_risk": 0.24},
        {"price_range": {"min": 40, "max": 55}, "unit": "PHP/kg", "sentiment": 0.61, "sentiment_status": "pending", "sentiment_as_of": "2026-09-28"},
        {"yield": {"min": 8000, "max": 10000}, "profit": {"conservative": 113000, "expected": 247500, "optimistic": 370000}},
        {"overall": 47, "overall_label": "Moderate", "weather": 32, "market": 58, "production": 45, "data": 51},
        [{"title": "Tomato Production Guide", "section": "Climate Requirements"}],
    )
    assert "247500" in text
    assert "Tomato Production Guide" in text
    assert "999999" not in text
