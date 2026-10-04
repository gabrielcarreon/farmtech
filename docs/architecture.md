# Crop Intelligence architecture

This is a local decision-support tool. Every analysis is a scenario with assumptions, not a promise of yield, price, or profit.

## Three engines

- The data engine answers "what is stored?": PostgreSQL tables for crops, yields, costs, prices, climate normals, and weather history.
- The RAG engine answers "what do the documents say?": heading-aware chunks, optional pgvector embeddings, and PostgreSQL full-text search. Ranked results are fused and returned as citations.
- The prediction engine answers "what range follows from the numbers?": deterministic weather, profit, and risk functions. Weights live in `scoring_profiles`. The language model never supplies the figures shown in an analysis.

## Degradation

The API probes the local AI service with a short timeout and one retry. If it is down:

- crop analysis still completes
- sentiment status is `pending`
- the latest `market_sentiment` row is shown when one exists, with its date
- document search falls back to full-text
- the explanation is a template that repeats engine numbers and document titles

Embedding and sentiment refresh jobs stay queued. A pending job is not an application outage.

## Provenance

Each `analyses` row stores the request, the full result, source ids, the scoring profile version, and model version strings. The result lists price and cost dates, whether each timeline day is a forecast or a climate normal, and the document titles used as evidence.

## Local AI

Run `uvicorn app.main:app --port 8100` from `ai/`, or `docker compose --profile ai up`. The service expects header `X-API-Key`. Sentiment uses a lexicon until a transformer model is plugged into `ai/app/services/models.py`. Embeddings use `sentence-transformers` when that package is installed, and a hashed 384-dimension vector otherwise. `/generate` calls Ollama only when `OLLAMA_BASE_URL` is set.

Do not port-forward the AI service. When the API moves to another machine, point `AI_SERVICE_URL` at a private tunnel (Tailscale or a Cloudflare named tunnel) that reaches port 8100, and keep the same API key.

## Run locally

```text
docker compose up --build
```

That starts PostgreSQL with pgvector on host port 5433, Redis, the API on port 8000, the ARQ worker, and the web app on port 3000. Port 5433 avoids colliding with a Postgres instance already listening on 5432. The first boot migrates and seeds five crops across Nueva Ecija, Bulacan, Laguna, and Pangasinan.

Copy `.env.example` to `.env` before running the API or AI service directly on the host. Weather comes from Open-Meteo and is cached in Redis. Days after the forecast window use the seeded monthly climate normals and are labeled `climatology`.

The bundled numbers and guide texts are sample data for the workflow, not official statistics.
