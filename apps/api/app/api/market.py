from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.entities import Crop, CropPrice, MarketArticle, MarketSentiment
from app.predictions.risk import price_volatility

router = APIRouter(prefix="/api/market")


@router.get("/prices")
def prices(crop_id: int = Query(...), region: str | None = None, db: Session = Depends(get_db)) -> dict:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="crop not found")
    stmt = select(CropPrice).where(CropPrice.crop_id == crop_id).order_by(CropPrice.date)
    if region:
        stmt = stmt.where(CropPrice.region == region)
    rows = db.scalars(stmt).all()
    values = [row.price for row in rows]
    return {
        "crop": crop.name,
        "unit": "PHP/kg",
        "latest": None if not rows else rows[-1].price,
        "average": None if not values else round(sum(values) / len(values), 2),
        "volatility": None if not values else price_volatility(values),
        "points": [
            {"date": row.date.isoformat(), "price": row.price, "market": row.market, "region": row.region, "source": row.source}
            for row in rows
        ],
    }


@router.get("/sentiment")
def sentiment(crop_id: int = Query(...), region: str | None = None, db: Session = Depends(get_db)) -> dict:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="crop not found")
    signal_stmt = select(MarketSentiment).where(MarketSentiment.crop_id == crop_id).order_by(MarketSentiment.date)
    article_stmt = select(MarketArticle).where(MarketArticle.crop_id == crop_id).order_by(MarketArticle.published_at)
    if region:
        signal_stmt = signal_stmt.where(MarketSentiment.region == region)
        article_stmt = article_stmt.where(MarketArticle.region == region)
    signals = db.scalars(signal_stmt).all()
    articles = db.scalars(article_stmt).all()
    return {
        "crop": crop.name,
        "signals": [
            {
                "date": row.date.isoformat(),
                "region": row.region,
                "positive_score": row.positive_score,
                "negative_score": row.negative_score,
                "neutral_score": row.neutral_score,
                "sentiment_index": row.sentiment_index,
                "article_count": row.article_count,
                "confidence": row.confidence,
            }
            for row in signals
        ],
        "articles": [
            {
                "id": row.id,
                "title": row.title,
                "source": row.source,
                "date": row.published_at.isoformat(),
                "crop": crop.name,
                "region": row.region,
                "sentiment": (row.sentiment or {}).get("sentiment"),
                "score": (row.sentiment or {}).get("score"),
                "confidence": (row.sentiment or {}).get("confidence"),
                "status": row.status,
            }
            for row in articles
        ],
    }
