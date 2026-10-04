from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AIUnavailable(Exception):
    pass


class AIClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.ai_service_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.ai_api_key
        self.timeout = timeout if timeout is not None else settings.ai_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    def is_healthy(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/health", headers=self._headers(), timeout=self.timeout)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def model_info(self) -> dict | None:
        try:
            response = httpx.get(f"{self.base_url}/model", headers=self._headers(), timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError as exc:
            logger.info("AI model info unavailable: %s", exc)
        return None

    def embed(self, texts: list[str]) -> dict:
        return self._post("/embeddings/generate", {"texts": texts}, max(self.timeout, 20))

    def analyze_sentiment(self, text: str) -> dict:
        return self._post("/sentiment/analyze", {"text": text}, self.timeout)

    def generate(self, prompt: str, context: list[str]) -> dict:
        try:
            return self._post("/generate", {"prompt": prompt, "context": context}, max(self.timeout, 30))
        except AIUnavailable as exc:
            if "503" in str(exc):
                raise AIUnavailable("llm_unavailable") from exc
            raise

    def _post(self, path: str, payload: dict, timeout: float) -> dict:
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = httpx.post(
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    json=payload,
                    timeout=timeout,
                )
                if response.status_code == 503:
                    raise AIUnavailable("503")
                response.raise_for_status()
                return response.json()
            except AIUnavailable:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
        raise AIUnavailable(str(last_error))


def resolve_sentiment(live: dict | None, stored: dict | None) -> dict:
    if live is not None:
        return {
            "status": "ready",
            "source": "live",
            "index": live.get("sentiment_index", live.get("index")),
            "as_of": live.get("as_of"),
            "confidence": live.get("confidence"),
            "article_count": live.get("article_count", 0),
        }
    if stored is not None:
        return {
            "status": "pending",
            "source": "stored",
            "index": stored.get("sentiment_index"),
            "as_of": stored.get("as_of"),
            "confidence": stored.get("confidence"),
            "article_count": stored.get("article_count", 0),
        }
    return {
        "status": "pending",
        "source": "none",
        "index": None,
        "as_of": None,
        "confidence": None,
        "article_count": 0,
    }
