from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://crop:crop@localhost:5433/crop_intelligence"
    redis_url: str = "redis://localhost:6379/0"
    ai_service_url: str = "http://localhost:8100"
    ai_api_key: str = "dev-ai-key"
    ollama_base_url: str = ""
    embedding_dimension: int = 384
    embedding_model: str = "all-MiniLM-L6-v2"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    cors_origins: str = "http://localhost:3000"
    prediction_model_version: str = "v0.1"
    seed_data_dir: str = ""
    weather_cache_seconds: int = 3600
    ai_timeout_seconds: float = 2.5
    rate_limit_per_minute: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def get_settings() -> Settings:
    return Settings()
