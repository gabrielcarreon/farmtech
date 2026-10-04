from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.entities import ImportJob
from app.services.import_service import ImportFailure, import_dataset

router = APIRouter(prefix="/api/data")


@router.post("/import")
async def create_import(
    file: UploadFile = File(...),
    kind: str = Form(...),
    source: str = Form(...),
    region: str | None = Form(None),
    crop: str | None = Form(None),
    province: str | None = Form(None),
    document_type: str | None = Form(None),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    content = await file.read()
    try:
        job = import_dataset(
            db,
            filename=file.filename or "upload",
            kind=kind,
            content=content,
            source=source,
            region=region,
            crop=crop,
            province=province,
            document_type=document_type,
            title=title,
        )
    except ImportFailure as exc:
        raise HTTPException(status_code=422, detail={"job_id": exc.job_id, "errors": exc.errors}) from exc
    if kind == "documents":
        await _enqueue_embeddings()
    return _job(job)


@router.get("/import/{job_id}")
def get_import(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="import not found")
    return _job(job)


def _job(job: ImportJob) -> dict:
    return {
        "id": job.id,
        "filename": job.filename,
        "kind": job.kind,
        "status": job.status,
        "errors": job.errors,
        "row_count": job.row_count,
        "metadata": job.metadata_json,
    }


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
