from __future__ import annotations

import hashlib
import math
import os
import re

POSITIVE = (
    "subsidy",
    "support",
    "harvest",
    "stable",
    "demand",
    "export",
    "recovery",
    "favorable",
    "surplus",
    "adequate",
    "firm",
    "improved",
)
NEGATIVE = (
    "drought",
    "flood",
    "typhoon",
    "pest",
    "blight",
    "shortage",
    "loss",
    "losses",
    "wilt",
    "storm",
    "damage",
    "delayed",
    "volatility",
)
TOPICS = {
    "price": ("price", "prices", "buying", "peso"),
    "supply": ("supply", "shortage", "harvest", "stocks"),
    "weather": ("rain", "typhoon", "flood", "drought", "storm"),
    "policy": ("subsidy", "government", "procurement"),
}
ENTITIES = (
    "tomato",
    "maize",
    "corn",
    "rice",
    "onion",
    "eggplant",
    "central luzon",
    "nueva ecija",
    "bulacan",
    "calabarzon",
    "laguna",
    "ilocos",
    "pangasinan",
)


def analyze_text(text: str) -> dict:
    tokens = re.findall(r"[a-z]+", text.lower())
    bag = " ".join(tokens)
    positive_hits = sum(bag.count(word) for word in POSITIVE)
    negative_hits = sum(bag.count(word) for word in NEGATIVE)
    total = positive_hits + negative_hits
    score = 0.0 if total == 0 else max(-1.0, min(1.0, (positive_hits - negative_hits) / total))
    if score > 0.15:
        label = "positive"
    elif score < -0.15:
        label = "negative"
    else:
        label = "neutral"
    confidence = 0.45 if total == 0 else min(0.9, 0.5 + total * 0.08)
    found_entities = [name for name in ENTITIES if name in text.lower()]
    topics = [name for name, words in TOPICS.items() if any(word in bag for word in words)]
    return {
        "sentiment": label,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "entities": found_entities,
        "topics": topics,
        "model": "lexicon-v1",
    }


def hash_embed(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    tokens = re.findall(r"[a-z0-9]+", text.lower()) or ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_texts(texts: list[str], dimension: int) -> tuple[list[list[float]], str]:
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)
        vectors = model.encode(texts, normalize_embeddings=True)
        converted = [list(map(float, vector[:dimension])) for vector in vectors]
        if converted and len(converted[0]) == dimension:
            return converted, model_name
    except Exception:
        pass
    return [hash_embed(text, dimension) for text in texts], "hash-fallback-v1"
