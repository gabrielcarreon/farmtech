from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sentiment.client import AIUnavailable


class OfflineAI:
    def __init__(self, *args, **kwargs):
        pass

    def is_healthy(self) -> bool:
        return False

    def model_info(self):
        return None

    def embed(self, texts):
        raise AIUnavailable("offline")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        health = test_client.get("/health/database")
        if health.status_code != 200:
            pytest.skip("PostgreSQL is not available for the analysis API test")
        crops = test_client.get("/api/crops")
        if crops.status_code != 200 or len(crops.json()) < 5:
            pytest.skip("seed data is not loaded")
        yield test_client


def test_analysis_is_stored_when_local_ai_is_offline(client, monkeypatch):
    monkeypatch.setattr("app.api.analysis.AIClient", OfflineAI)
    response = client.post(
        "/api/analysis/crops",
        json={
            "location": {"province": "Nueva Ecija", "latitude": 15.48, "longitude": 120.59},
            "farm_size_hectares": 1,
            "planting_date": "2026-10-15",
            "horizon_months": 6,
            "available_capital": 200000,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"]
    assert body["crops"]
    assert all(crop["sentiment"]["status"] == "pending" for crop in body["crops"])
    assert "not guarantees" in body["disclaimer"]
    stored = client.get(f"/api/analysis/{body['id']}")
    assert stored.status_code == 200
    assert stored.json()["id"] == body["id"]
    assert stored.json()["model_versions"]["prediction"]


def test_hybrid_search_finds_the_tomato_guide(client):
    from app.core.db import SessionLocal
    from app.rag.retrieve import search_chunks

    session = SessionLocal()
    try:
        evidence = search_chunks(
            session,
            "rainfall requirements for tomatoes in Central Luzon",
            crop="Tomato",
            region="Central Luzon",
        )
    finally:
        session.close()
    assert any(item["title"] == "Tomato Production Guide" and item["document_id"] for item in evidence)
