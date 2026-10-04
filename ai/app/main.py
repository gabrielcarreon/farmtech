from __future__ import annotations

import os

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.models import analyze_text, embed_texts

app = FastAPI(title="Crop Intelligence Local AI", version="0.1.0")


class SentimentIn(BaseModel):
    text: str = Field(min_length=1)


class EmbedIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=1)
    context: list[str] = Field(default_factory=list)


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("AI_API_KEY", "dev-ai-key")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")


def _dimension() -> int:
    return int(os.environ.get("EMBEDDING_DIMENSION", "384"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "local-ai"}


@app.get("/model")
def model(_auth: None = Depends(require_key)) -> dict:
    return {
        "sentiment": "lexicon-v1",
        "embedding": os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        "embedding_fallback": "hash-fallback-v1",
        "llm": os.environ.get("OLLAMA_MODEL", "llama3.2") if os.environ.get("OLLAMA_BASE_URL") else "unavailable",
    }


@app.post("/sentiment/analyze")
def sentiment(body: SentimentIn, _auth: None = Depends(require_key)) -> dict:
    return analyze_text(body.text)


@app.post("/embeddings/generate")
def embeddings(body: EmbedIn, _auth: None = Depends(require_key)) -> dict:
    vectors, model_name = embed_texts(body.texts, _dimension())
    return {"embeddings": vectors, "model": model_name, "dimension": _dimension()}


@app.post("/generate")
def generate(body: GenerateIn, _auth: None = Depends(require_key)) -> dict:
    base = os.environ.get("OLLAMA_BASE_URL", "").rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="llm_unavailable")
    prompt = (
        "Answer only from the agricultural context. Do not invent prices, yields, weather, or sources. "
        "If the context is insufficient, say so.\n\n"
        f"Question: {body.prompt}\n\nContext:\n" + "\n\n".join(body.context)
    )
    try:
        response = httpx.post(
            f"{base}/api/generate",
            json={"model": os.environ.get("OLLAMA_MODEL", "llama3.2"), "prompt": prompt, "stream": False},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="llm_unavailable") from exc
    return {"answer": response.json().get("response", ""), "model": os.environ.get("OLLAMA_MODEL", "llama3.2")}
