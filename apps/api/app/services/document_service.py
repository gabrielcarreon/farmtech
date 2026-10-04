from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk


def _crop_of(document: Document) -> str | None:
    meta = document.metadata_json or {}
    return meta.get("crop")


def _chunk_embedding_status(chunk: DocumentChunk) -> str:
    meta = chunk.metadata_json or {}
    if chunk.embedding is not None:
        return "ready"
    return meta.get("embedding_status") or "pending"


def embedding_status_for_counts(chunk_count: int, embedded_count: int) -> str:
    if chunk_count == 0:
        return "pending"
    if embedded_count == 0:
        return "pending"
    if embedded_count >= chunk_count:
        return "ready"
    return "partial"


def list_documents(
    db: Session,
    *,
    crop: str | None = None,
    region: str | None = None,
    q: str | None = None,
) -> list[dict]:
    chunk_count = func.count(DocumentChunk.id).label("chunk_count")
    embedded_count = func.count(DocumentChunk.embedding).label("embedded_count")
    stmt = (
        select(Document, chunk_count, embedded_count)
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    )
    if crop:
        stmt = stmt.where(func.lower(Document.metadata_json["crop"].astext) == crop.lower())
    if region:
        stmt = stmt.where(func.lower(func.coalesce(Document.region, "")) == region.lower())
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Document.title.ilike(pattern),
                Document.source.ilike(pattern),
                Document.document_type.ilike(pattern),
            )
        )
    rows = db.execute(stmt).all()
    return [
        {
            "id": document.id,
            "title": document.title,
            "source": document.source,
            "document_type": document.document_type,
            "region": document.region,
            "province": document.province,
            "crop": _crop_of(document),
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "chunk_count": int(chunks or 0),
            "embedded_count": int(embedded or 0),
            "embedding_status": embedding_status_for_counts(int(chunks or 0), int(embedded or 0)),
        }
        for document, chunks, embedded in rows
    ]


def get_document(db: Session, document_id: int) -> dict | None:
    document = db.get(Document, document_id)
    if document is None:
        return None
    chunks = db.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
    ).all()
    embedded = sum(1 for chunk in chunks if chunk.embedding is not None)
    return {
        "id": document.id,
        "title": document.title,
        "source": document.source,
        "source_url": document.source_url,
        "document_type": document.document_type,
        "publication_date": document.publication_date.isoformat() if document.publication_date else None,
        "region": document.region,
        "province": document.province,
        "language": document.language,
        "crop": _crop_of(document),
        "metadata": document.metadata_json or {},
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "chunk_count": len(chunks),
        "embedded_count": embedded,
        "embedding_status": embedding_status_for_counts(len(chunks), embedded),
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "section": (chunk.metadata_json or {}).get("section"),
                "content": chunk.content,
                "embedding_status": _chunk_embedding_status(chunk),
            }
            for chunk in chunks
        ],
    }


def update_document(
    db: Session,
    document_id: int,
    *,
    title: str | None = None,
    source: str | None = None,
    document_type: str | None = None,
    region: str | None = None,
    province: str | None = None,
    crop: str | None = None,
) -> dict | None:
    document = db.get(Document, document_id)
    if document is None:
        return None
    if title is not None:
        document.title = title.strip() or document.title
    if source is not None:
        document.source = source.strip() or None
    if document_type is not None:
        document.document_type = document_type.strip() or None
    if region is not None:
        document.region = region.strip() or None
    if province is not None:
        document.province = province.strip() or None
    if crop is not None:
        cleaned = crop.strip() or None
        document.metadata_json = {**(document.metadata_json or {}), "crop": cleaned}
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all()
    for chunk in chunks:
        meta = {**(chunk.metadata_json or {})}
        if region is not None:
            meta["region"] = document.region
        if province is not None:
            meta["province"] = document.province
        if crop is not None:
            meta["crop"] = (document.metadata_json or {}).get("crop")
        chunk.metadata_json = meta
    db.commit()
    return get_document(db, document_id)


def delete_document(db: Session, document_id: int) -> bool:
    document = db.get(Document, document_id)
    if document is None:
        return False
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    db.delete(document)
    db.commit()
    return True


def reembed_document(db: Session, document_id: int) -> dict | None:
    document = db.get(Document, document_id)
    if document is None:
        return None
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id)).all()
    for chunk in chunks:
        chunk.embedding = None
        chunk.metadata_json = {**(chunk.metadata_json or {}), "embedding_status": "pending"}
    db.commit()
    return get_document(db, document_id)
