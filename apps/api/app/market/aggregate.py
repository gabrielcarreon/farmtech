from __future__ import annotations


def aggregate_sentiment(scores: list[dict]) -> dict | None:
    if not scores:
        return None
    values = [float(item["score"]) for item in scores]
    confidences = [float(item.get("confidence", 0.5)) for item in scores]
    labels = [item.get("sentiment", "neutral") for item in scores]
    count = len(values)
    return {
        "positive_score": round(sum(max(value, 0.0) for value in values) / count, 4),
        "negative_score": round(sum(max(-value, 0.0) for value in values) / count, 4),
        "neutral_score": round(sum(1 for label in labels if label == "neutral") / count, 4),
        "sentiment_index": round(sum(values) / count, 4),
        "article_count": count,
        "confidence": round(sum(confidences) / count, 4),
    }
