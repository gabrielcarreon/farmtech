from __future__ import annotations

import re

_STOP = {
    "what",
    "when",
    "where",
    "which",
    "this",
    "that",
    "with",
    "from",
    "have",
    "does",
    "about",
    "into",
    "they",
    "them",
    "then",
    "than",
    "their",
    "your",
    "will",
    "would",
}


def full_text_query(text: str) -> str | None:
    tokens: list[str] = []
    seen = set()
    for raw in re.findall(r"[A-Za-z]{4,}", text.lower()):
        if raw in _STOP or raw in seen:
            continue
        seen.add(raw)
        tokens.append(raw)
    if not tokens:
        return None
    return " | ".join(tokens[:12])


def build_metadata_filters(
    crop: str | None = None,
    region: str | None = None,
    province: str | None = None,
    season: str | None = None,
    document_type: str | None = None,
    year: int | None = None,
) -> dict:
    raw = {
        "crop": crop,
        "region": region,
        "province": province,
        "season": season,
        "document_type": document_type,
        "year": year,
    }
    return {key: value for key, value in raw.items() if value is not None and value != ""}


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60, limit: int = 5) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores, key=lambda item: (-scores[item], item))
    return ordered[:limit]
