"""Crop Intelligence schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    region VARCHAR(120) NOT NULL,
    province VARCHAR(120) NOT NULL UNIQUE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL
);

CREATE TABLE climate_normals (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    temperature_min DOUBLE PRECISION NOT NULL,
    temperature_max DOUBLE PRECISION NOT NULL,
    rainfall_mm DOUBLE PRECISION NOT NULL,
    humidity DOUBLE PRECISION,
    UNIQUE (location_id, month)
);

CREATE TABLE crops (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    scientific_name VARCHAR(160),
    category VARCHAR(80),
    description TEXT,
    growing_days_min INTEGER NOT NULL,
    growing_days_max INTEGER NOT NULL,
    optimal_temperature_min DOUBLE PRECISION NOT NULL,
    optimal_temperature_max DOUBLE PRECISION NOT NULL,
    optimal_rainfall_min DOUBLE PRECISION NOT NULL,
    optimal_rainfall_max DOUBLE PRECISION NOT NULL,
    water_requirement VARCHAR(240),
    soil_requirements TEXT,
    suitable_months JSONB NOT NULL DEFAULT '[]'::jsonb,
    production_sensitivity DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE crop_varieties (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    growing_days INTEGER NOT NULL,
    yield_min DOUBLE PRECISION NOT NULL,
    yield_max DOUBLE PRECISION NOT NULL,
    yield_unit VARCHAR(40) NOT NULL DEFAULT 'kg/ha',
    temperature_requirements JSONB,
    rainfall_requirements JSONB
);

CREATE TABLE crop_regions (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    region VARCHAR(120) NOT NULL,
    province VARCHAR(120),
    suitable BOOLEAN NOT NULL DEFAULT TRUE,
    historical_yield DOUBLE PRECISION,
    yield_unit VARCHAR(40),
    UNIQUE (crop_id, region, province)
);

CREATE TABLE crop_costs (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    region VARCHAR(120) NOT NULL,
    province VARCHAR(120),
    seed_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    fertilizer_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    labor_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    pesticide_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    irrigation_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    equipment_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    other_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_cost DOUBLE PRECISION NOT NULL,
    effective_date DATE NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'PHP'
);

CREATE TABLE crop_prices (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    market VARCHAR(160) NOT NULL,
    region VARCHAR(120) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    unit VARCHAR(40) NOT NULL,
    date DATE NOT NULL,
    source VARCHAR(240) NOT NULL,
    UNIQUE (crop_id, market, region, date, source)
);

CREATE TABLE crop_yields (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    region VARCHAR(120) NOT NULL,
    province VARCHAR(120),
    yield_value DOUBLE PRECISION NOT NULL,
    yield_unit VARCHAR(40) NOT NULL,
    date DATE NOT NULL,
    source VARCHAR(240) NOT NULL,
    UNIQUE (crop_id, region, province, date, source)
);

CREATE TABLE weather_history (
    id SERIAL PRIMARY KEY,
    location VARCHAR(160) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    date DATE NOT NULL,
    temperature_min DOUBLE PRECISION,
    temperature_max DOUBLE PRECISION,
    rainfall DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    weather_condition VARCHAR(80),
    source VARCHAR(160) NOT NULL,
    UNIQUE (location, date)
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(300) NOT NULL,
    source VARCHAR(240),
    source_url TEXT,
    document_type VARCHAR(80),
    publication_date DATE,
    region VARCHAR(120),
    province VARCHAR(120),
    language VARCHAR(16) NOT NULL DEFAULT 'en',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX document_chunks_search_idx ON document_chunks USING gin (search_vector);

CREATE TABLE market_articles (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER REFERENCES crops(id) ON DELETE SET NULL,
    region VARCHAR(120),
    title VARCHAR(300) NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(240) NOT NULL,
    published_at DATE NOT NULL,
    sentiment JSONB,
    status VARCHAR(40) NOT NULL DEFAULT 'pending'
);

CREATE TABLE market_sentiment (
    id SERIAL PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    region VARCHAR(120) NOT NULL,
    date DATE NOT NULL,
    positive_score DOUBLE PRECISION NOT NULL,
    negative_score DOUBLE PRECISION NOT NULL,
    neutral_score DOUBLE PRECISION NOT NULL,
    sentiment_index DOUBLE PRECISION NOT NULL,
    article_count INTEGER NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    UNIQUE (crop_id, region, date)
);

CREATE TABLE scoring_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    version VARCHAR(40) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    weights JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    input_snapshot JSONB NOT NULL,
    result JSONB NOT NULL,
    scoring_version VARCHAR(40) NOT NULL,
    prediction_model_version VARCHAR(40) NOT NULL,
    sentiment_model_version VARCHAR(80),
    embedding_model_version VARCHAR(80),
    llm_model_version VARCHAR(80),
    source_ids JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE import_jobs (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(300) NOT NULL,
    kind VARCHAR(40) NOT NULL,
    status VARCHAR(40) NOT NULL,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    row_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

DOWNGRADE_TABLES = [
    "import_jobs",
    "analyses",
    "scoring_profiles",
    "market_sentiment",
    "market_articles",
    "document_chunks",
    "documents",
    "weather_history",
    "crop_yields",
    "crop_prices",
    "crop_costs",
    "crop_regions",
    "crop_varieties",
    "crops",
    "climate_normals",
    "locations",
]


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    for table in DOWNGRADE_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
