from __future__ import annotations

import logging
from datetime import date

from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.market.aggregate import aggregate_sentiment
from app.models.entities import DocumentChunk, MarketArticle, MarketSentiment
from app.sentiment.client import AIClient, AIUnavailable

logger = logging.getLogger(__name__)


async def embed_pending_chunks(ctx) -> dict:
    settings = get_settings()
    ai = AIClient()
    if not ai.is_healthy():
        return {"status": "pending", "embedded": 0}
    db = SessionLocal()
    try:
        rows = list(
            db.scalars(select(DocumentChunk).where(DocumentChunk.embedding.is_(None)).limit(32))
        )
        if not rows:
            return {"status": "ready", "embedded": 0}
        try:
            payload = ai.embed([row.content for row in rows])
        except AIUnavailable:
            return {"status": "pending", "embedded": 0}
        vectors = payload.get("embeddings") or []
        model = payload.get("model")
        embedded = 0
        for row, vector in zip(rows, vectors):
            if len(vector) != settings.embedding_dimension:
                continue
            row.embedding = vector
            row.metadata_json = {**(row.metadata_json or {}), "embedding_model": model, "embedding_status": "ready"}
            embedded += 1
        db.commit()
        return {"status": "ready", "embedded": embedded, "model": model}
    finally:
        db.close()


async def refresh_market_sentiment(ctx) -> dict:
    ai = AIClient()
    if not ai.is_healthy():
        return {"status": "pending"}
    db = SessionLocal()
    try:
        articles = list(db.scalars(select(MarketArticle)))
        groups: dict[tuple[int, str], list[dict]] = {}
        scored = 0
        for article in articles:
            try:
                sentiment = ai.analyze_sentiment(article.content)
            except AIUnavailable:
                return {"status": "pending", "scored": scored}
            article.sentiment = sentiment
            article.status = "ready"
            scored += 1
            if article.crop_id and article.region:
                groups.setdefault((article.crop_id, article.region), []).append(sentiment)
        today = date.today()
        for (crop_id, region), scores in groups.items():
            summary = aggregate_sentiment(scores)
            if summary is None:
                continue
            existing = db.scalar(
                select(MarketSentiment).where(
                    MarketSentiment.crop_id == crop_id,
                    MarketSentiment.region == region,
                    MarketSentiment.date == today,
                )
            )
            if existing is None:
                db.add(MarketSentiment(crop_id=crop_id, region=region, date=today, **summary))
            else:
                for field, value in summary.items():
                    setattr(existing, field, value)
        db.commit()
        return {"status": "ready", "scored": scored}
    finally:
        db.close()


class WorkerSettings:
    functions = [embed_pending_chunks, refresh_market_sentiment]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs = [
        cron(embed_pending_chunks, minute={0, 15, 30, 45}),
        cron(refresh_market_sentiment, minute={5, 35}),
    ]
