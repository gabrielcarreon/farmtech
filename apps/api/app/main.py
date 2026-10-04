import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.crops import router as crops_router
from app.api.documents import router as documents_router
from app.api.health import rate_limit_middleware_factory, router as health_router
from app.api.imports import router as imports_router
from app.api.market import router as market_router
from app.api.rag import router as rag_router
from app.api.weather import router as weather_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="Crop Intelligence API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(rate_limit_middleware_factory())
app.include_router(health_router)
app.include_router(crops_router)
app.include_router(weather_router)
app.include_router(market_router)
app.include_router(rag_router)
app.include_router(documents_router)
app.include_router(analysis_router)
app.include_router(imports_router)
