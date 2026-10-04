from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import document_service

router = APIRouter(prefix="/api/rag/documents")


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    source: str | None = Field(default=None, max_length=240)
    document_type: str | None = Field(default=None, max_length=80)
    region: str | None = None
    province: str | None = None
    crop: str | None = None


@router.get("")
def list_documents(
    crop: str | None = Query(None),
    region: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    return {"documents": document_service.list_documents(db, crop=crop, region=region, q=q)}


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = document_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.patch("/{document_id}")
def patch_document(document_id: int, body: DocumentUpdate, db: Session = Depends(get_db)) -> dict:
    payload = body.model_dump(exclude_unset=True)
    document = document_service.update_document(db, document_id, **payload)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.delete("/{document_id}")
def remove_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    if not document_service.delete_document(db, document_id):
        raise HTTPException(status_code=404, detail="document not found")
    return {"status": "deleted", "id": document_id}


@router.post("/{document_id}/reembed")
async def reembed_document(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = document_service.reembed_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    await _enqueue_embeddings()
    return document


async def _enqueue_embeddings() -> None:
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import get_settings

        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        await pool.enqueue_job("embed_pending_chunks")
        await pool.aclose()
    except Exception:
        return
