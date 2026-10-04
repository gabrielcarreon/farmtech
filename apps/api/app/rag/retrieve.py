from __future__ import annotations

from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.rag.filters import build_metadata_filters, full_text_query, reciprocal_rank_fusion


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def search_chunks(
    session: Session,
    query: str,
    *,
    crop: str | None = None,
    region: str | None = None,
    province: str | None = None,
    document_type: str | None = None,
    embedding: list[float] | None = None,
    candidate_k: int = 15,
    keep: int = 5,
) -> list[dict]:
    filters = build_metadata_filters(crop=crop, region=region, province=province, document_type=document_type)
    metadata_sql = """
        (CAST(:crop AS text) IS NULL OR lower(document_chunks.metadata->>'crop') = lower(:crop))
        AND (
            CAST(:region AS text) IS NULL
            OR lower(coalesce(document_chunks.metadata->>'region', '')) = lower(:region)
            OR coalesce(document_chunks.metadata->>'region', '') = ''
        )
        AND (
            CAST(:province AS text) IS NULL
            OR lower(coalesce(document_chunks.metadata->>'province', '')) = lower(:province)
            OR coalesce(document_chunks.metadata->>'province', '') = ''
        )
        AND (
            CAST(:document_type AS text) IS NULL
            OR lower(coalesce(documents.document_type, '')) = lower(:document_type)
        )
    """
    params = {
        "query": query,
        "crop": filters.get("crop"),
        "region": filters.get("region"),
        "province": filters.get("province"),
        "document_type": filters.get("document_type"),
        "candidate_k": candidate_k,
    }
    text_query = full_text_query(query)
    text_ids: list[int] = []
    if text_query:
        text_ids = [
            row[0]
            for row in session.execute(
                text(
                    f"""
                    SELECT document_chunks.id
                    FROM document_chunks
                    JOIN documents ON documents.id = document_chunks.document_id,
                         to_tsquery('english', :tsquery) q
                    WHERE document_chunks.search_vector @@ q
                      AND {metadata_sql}
                    ORDER BY ts_rank(document_chunks.search_vector, q) DESC
                    LIMIT :candidate_k
                    """
                ),
                {**params, "tsquery": text_query},
            )
        ]
    vector_ids: list[int] = []
    if embedding:
        vector_params = dict(params)
        vector_params["embedding"] = _vector_literal(embedding)
        vector_ids = [
            row[0]
            for row in session.execute(
                text(
                    f"""
                    SELECT document_chunks.id
                    FROM document_chunks
                    JOIN documents ON documents.id = document_chunks.document_id
                    WHERE document_chunks.embedding IS NOT NULL
                      AND {metadata_sql}
                    ORDER BY document_chunks.embedding <=> CAST(:embedding AS vector)
                    LIMIT :candidate_k
                    """
                ),
                vector_params,
            )
        ]
    rankings = [ranking for ranking in (vector_ids, text_ids) if ranking]
    if not rankings:
        return []
    chosen = reciprocal_rank_fusion(rankings, limit=keep)
    if not chosen:
        return []
    rows = session.execute(
        text(
            """
            SELECT document_chunks.id, document_chunks.document_id, document_chunks.content,
                   document_chunks.metadata, documents.title, documents.source, documents.document_type
            FROM document_chunks
            JOIN documents ON documents.id = document_chunks.document_id
            WHERE document_chunks.id = ANY(:ids)
            """
        ).bindparams(bindparam("ids", type_=ARRAY(Integer))),
        {"ids": chosen},
    ).mappings().all()
    by_id = {row["id"]: row for row in rows}
    evidence = []
    for chunk_id in chosen:
        row = by_id.get(chunk_id)
        if row is None:
            continue
        meta = row["metadata"] or {}
        content = row["content"]
        evidence.append(
            {
                "chunk_id": row["id"],
                "document_id": row["document_id"],
                "title": row["title"],
                "source": row["source"],
                "document_type": row["document_type"],
                "section": meta.get("section"),
                "crop": meta.get("crop"),
                "region": meta.get("region"),
                "excerpt": content[:700],
            }
        )
    return evidence
