from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.rag.retrieve import search_chunks
from app.sentiment.client import AIClient, AIUnavailable

router = APIRouter(prefix="/api/rag")


class SearchRequest(BaseModel):
    query: str = Field(min_length=3)
    crop: str | None = None
    region: str | None = None
    province: str | None = None
    document_type: str | None = None


class AnalyzeRequest(SearchRequest):
    pass


@router.post("/search")
def rag_search(body: SearchRequest, db: Session = Depends(get_db)) -> dict:
    evidence = search_chunks(
        db,
        body.query,
        crop=body.crop,
        region=body.region,
        province=body.province,
        document_type=body.document_type,
        embedding=_embedding(body.query),
    )
    return {"query": body.query, "evidence": evidence, "llm": "not_used"}


@router.post("/analyze")
def rag_analyze(body: AnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    evidence = search_chunks(
        db,
        body.query,
        crop=body.crop,
        region=body.region,
        province=body.province,
        document_type=body.document_type,
        embedding=_embedding(body.query),
    )
    context = [item["excerpt"] for item in evidence]
    answer = None
    llm_status = "unavailable"
    if context:
        try:
            generated = AIClient().generate(body.query, context)
            answer = generated.get("answer")
            llm_status = "ok"
        except AIUnavailable:
            answer = _template_answer(body.query, evidence)
            llm_status = "template"
    else:
        answer = "No stored agricultural document matched this question, so there is no grounded answer."
        llm_status = "no_evidence"
    return {"query": body.query, "answer": answer, "evidence": evidence, "llm": llm_status}


def _embedding(query: str) -> list[float] | None:
    client = AIClient()
    if not client.is_healthy():
        return None
    try:
        payload = client.embed([query])
    except AIUnavailable:
        return None
    vectors = payload.get("embeddings") or []
    return vectors[0] if vectors else None


def _template_answer(query: str, evidence: list[dict]) -> str:
    lines = [
        f"Grounded notes for: {query}",
        "The local language model is unavailable, so this answer quotes retrieved passages only.",
        "",
    ]
    for item in evidence:
        section = f" ({item['section']})" if item.get("section") else ""
        lines.append(f"{item['title']}{section}")
        lines.append(item["excerpt"])
        lines.append("")
    return "\n".join(lines).strip()
