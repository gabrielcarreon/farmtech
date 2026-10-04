from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(120))
    province: Mapped[str] = mapped_column(String(120), unique=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    climate_normals: Mapped[list["ClimateNormal"]] = relationship(back_populates="location")


class ClimateNormal(Base):
    __tablename__ = "climate_normals"
    __table_args__ = (UniqueConstraint("location_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    month: Mapped[int] = mapped_column(Integer)
    temperature_min: Mapped[float] = mapped_column(Float)
    temperature_max: Mapped[float] = mapped_column(Float)
    rainfall_mm: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    location: Mapped[Location] = relationship(back_populates="climate_normals")


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    scientific_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    growing_days_min: Mapped[int] = mapped_column(Integer)
    growing_days_max: Mapped[int] = mapped_column(Integer)
    optimal_temperature_min: Mapped[float] = mapped_column(Float)
    optimal_temperature_max: Mapped[float] = mapped_column(Float)
    optimal_rainfall_min: Mapped[float] = mapped_column(Float)
    optimal_rainfall_max: Mapped[float] = mapped_column(Float)
    water_requirement: Mapped[str | None] = mapped_column(String(240), nullable=True)
    soil_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    suitable_months: Mapped[list] = mapped_column(JSONB, default=list)
    production_sensitivity: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    varieties: Mapped[list["CropVariety"]] = relationship(back_populates="crop")
    regions: Mapped[list["CropRegion"]] = relationship(back_populates="crop")


class CropVariety(Base):
    __tablename__ = "crop_varieties"

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    growing_days: Mapped[int] = mapped_column(Integer)
    yield_min: Mapped[float] = mapped_column(Float)
    yield_max: Mapped[float] = mapped_column(Float)
    yield_unit: Mapped[str] = mapped_column(String(40), default="kg/ha")
    temperature_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rainfall_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    crop: Mapped[Crop] = relationship(back_populates="varieties")


class CropRegion(Base):
    __tablename__ = "crop_regions"
    __table_args__ = (UniqueConstraint("crop_id", "region", "province"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    region: Mapped[str] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    suitable: Mapped[bool] = mapped_column(Boolean, default=True)
    historical_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    yield_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    crop: Mapped[Crop] = relationship(back_populates="regions")


class CropCost(Base):
    __tablename__ = "crop_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    region: Mapped[str] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seed_cost: Mapped[float] = mapped_column(Float, default=0)
    fertilizer_cost: Mapped[float] = mapped_column(Float, default=0)
    labor_cost: Mapped[float] = mapped_column(Float, default=0)
    pesticide_cost: Mapped[float] = mapped_column(Float, default=0)
    irrigation_cost: Mapped[float] = mapped_column(Float, default=0)
    equipment_cost: Mapped[float] = mapped_column(Float, default=0)
    other_cost: Mapped[float] = mapped_column(Float, default=0)
    total_cost: Mapped[float] = mapped_column(Float)
    effective_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8), default="PHP")


class CropPrice(Base):
    __tablename__ = "crop_prices"
    __table_args__ = (UniqueConstraint("crop_id", "market", "region", "date", "source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    market: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(120))
    price: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(240))


class CropYield(Base):
    __tablename__ = "crop_yields"
    __table_args__ = (UniqueConstraint("crop_id", "region", "province", "date", "source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    region: Mapped[str] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    yield_value: Mapped[float] = mapped_column(Float)
    yield_unit: Mapped[str] = mapped_column(String(40))
    date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(240))


class WeatherHistory(Base):
    __tablename__ = "weather_history"
    __table_args__ = (UniqueConstraint("location", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    date: Mapped[date] = mapped_column(Date)
    temperature_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_condition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(160))


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
    )
    document: Mapped[Document] = relationship(back_populates="chunks")


class MarketArticle(Base):
    __tablename__ = "market_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crops.id", ondelete="SET NULL"), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(240))
    published_at: Mapped[date] = mapped_column(Date)
    sentiment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")


class MarketSentiment(Base):
    __tablename__ = "market_sentiment"
    __table_args__ = (UniqueConstraint("crop_id", "region", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    region: Mapped[str] = mapped_column(String(120))
    date: Mapped[date] = mapped_column(Date)
    positive_score: Mapped[float] = mapped_column(Float)
    negative_score: Mapped[float] = mapped_column(Float)
    neutral_score: Mapped[float] = mapped_column(Float)
    sentiment_index: Mapped[float] = mapped_column(Float)
    article_count: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)


class ScoringProfile(Base):
    __tablename__ = "scoring_profiles"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    weights: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    scoring_version: Mapped[str] = mapped_column(String(40))
    prediction_model_version: Mapped[str] = mapped_column(String(40))
    sentiment_model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    llm_model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_ids: Mapped[dict] = mapped_column(JSONB, default=dict)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40))
    errors: Mapped[list] = mapped_column(JSONB, default=list)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
