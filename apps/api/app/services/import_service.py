from __future__ import annotations

import csv
import io
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import DependencyError, PdfReadError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import Crop, CropPrice, CropYield, Document, DocumentChunk, ImportJob, WeatherHistory
from app.rag.chunking import chunk_text
from app.services.validation import RowError, validate_price_row, validate_weather_row, validate_yield_row

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# #region agent log
_DEBUG_LOG = Path(__file__).resolve().parents[4] / "debug-cc5a38.log"


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "cc5a38",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


# #endregion


class ImportFailure(Exception):
    def __init__(self, job_id: int, errors: list[dict]):
        super().__init__("import failed validation")
        self.job_id = job_id
        self.errors = errors


def read_upload(filename: str, content: bytes) -> str:
    if len(content) > MAX_UPLOAD_BYTES:
        raise RowError(0, "file exceeds the 10 MB limit")
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        # #region agent log
        crypto_ok = False
        try:
            import cryptography  # noqa: F401

            crypto_ok = True
        except Exception:
            crypto_ok = False
        _agent_log(
            "A",
            "import_service.py:read_upload:pdf_start",
            "pdf upload received",
            {
                "filename": filename,
                "size": len(content),
                "header": content[:8].hex() if content else "",
                "cryptography_installed": crypto_ok,
            },
        )
        # #endregion
        try:
            reader = PdfReader(io.BytesIO(content))
            # #region agent log
            _agent_log(
                "B",
                "import_service.py:read_upload:pdf_meta",
                "pdf reader opened",
                {
                    "is_encrypted": bool(getattr(reader, "is_encrypted", False)),
                    "page_count_callable": True,
                },
            )
            # #endregion
            pages = []
            for index, page in enumerate(reader.pages):
                pages.append(page.extract_text() or "")
                if index == 0:
                    # #region agent log
                    _agent_log(
                        "B",
                        "import_service.py:read_upload:first_page",
                        "extracted first page",
                        {"chars": len(pages[0])},
                    )
                    # #endregion
            return "\n".join(pages)
        except DependencyError as exc:
            # #region agent log
            _agent_log(
                "A",
                "import_service.py:read_upload:dependency",
                "pdf dependency missing",
                {"error": str(exc), "cryptography_installed": crypto_ok},
            )
            # #endregion
            raise RowError(
                0,
                "This PDF uses AES encryption. Install the cryptography package on the API, or upload an unencrypted PDF/TXT/MD file.",
            ) from exc
        except PdfReadError as exc:
            # #region agent log
            _agent_log("D", "import_service.py:read_upload:pdf_read", "pdf unreadable", {"error": str(exc)})
            # #endregion
            raise RowError(0, f"Could not read PDF: {exc}") from exc
        except Exception as exc:
            # #region agent log
            _agent_log(
                "E",
                "import_service.py:read_upload:pdf_other",
                "unexpected pdf failure",
                {"error": str(exc), "type": type(exc).__name__},
            )
            # #endregion
            raise
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RowError(0, "text files must be UTF-8") from exc

def _records_from_text(kind: str, filename: str, text: str) -> list[dict]:
    lowered = filename.lower()
    if kind == "documents" or lowered.endswith(".pdf") or lowered.endswith(".txt") or lowered.endswith(".md"):
        return [{"content": text}]
    if lowered.endswith(".json"):
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload.get("rows") or [payload]
        if not isinstance(payload, list):
            raise RowError(0, "JSON import must be a list of rows")
        return payload
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _fail(db: Session, job: ImportJob, errors: list[dict]) -> None:
    job.status = "failed"
    job.errors = errors
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    raise ImportFailure(job.id, errors)


def import_dataset(
    db: Session,
    *,
    filename: str,
    kind: str,
    content: bytes,
    source: str,
    region: str | None = None,
    crop: str | None = None,
    province: str | None = None,
    document_type: str | None = None,
    title: str | None = None,
) -> ImportJob:
    job = ImportJob(
        filename=filename,
        kind=kind,
        status="pending",
        errors=[],
        metadata_json={"source": source, "region": region, "crop": crop},
    )
    db.add(job)
    db.flush()
    try:
        text = read_upload(filename, content)
        rows = _records_from_text(kind, filename, text)
    except (RowError, json.JSONDecodeError, csv.Error) as exc:
        message = exc.message if isinstance(exc, RowError) else str(exc)
        row = exc.row if isinstance(exc, RowError) else 0
        _fail(db, job, [{"row": row, "message": message}])
    if not rows:
        _fail(db, job, [{"row": 0, "message": "file has no records"}])

    if kind == "documents":
        return _import_document(db, job, text if filename.lower().endswith((".txt", ".md", ".pdf")) else _document_body(rows), source, region, crop, province, document_type, title or filename)
    validators = {"prices": validate_price_row, "yields": validate_yield_row, "weather": validate_weather_row}
    if kind not in validators:
        _fail(db, job, [{"row": 0, "message": "kind must be prices, yields, weather, or documents"}])
    parsed, errors = _parse_rows(rows, validators[kind])
    if errors:
        _fail(db, job, errors)
    duplicates = _existing_duplicates(db, kind, parsed)
    if duplicates:
        _fail(db, job, duplicates)
    try:
        if kind == "prices":
            _insert_prices(db, parsed)
        elif kind == "yields":
            _insert_yields(db, parsed)
        else:
            _insert_weather(db, parsed)
    except IntegrityError:
        db.rollback()
        job.status = "failed"
        job.errors = [{"row": 0, "message": "duplicate record already stored"}]
        db.add(job)
        db.commit()
        raise ImportFailure(job.id, job.errors)
    job.status = "ready"
    job.row_count = len(parsed)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    return job


def _document_body(rows: list[dict]) -> str:
    if rows and "content" in rows[0]:
        return "\n\n".join(row.get("content") or "" for row in rows)
    return json.dumps(rows)


def _parse_rows(rows: list[dict], validator) -> tuple[list[dict], list[dict]]:
    parsed = []
    errors = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        try:
            item = validator(row, index)
            key = tuple(sorted((field, str(value)) for field, value in item.items()))
            if key in seen:
                raise RowError(index, "duplicate record in file")
            seen.add(key)
            parsed.append(item)
        except RowError as exc:
            errors.append({"row": exc.row, "message": exc.message})
    return parsed, errors


def _crop_id(db: Session, name: str, index: int) -> int:
    crop = db.scalar(select(Crop).where(Crop.name.ilike(name)))
    if crop is None:
        raise RowError(index, f"unknown crop '{name}'")
    return crop.id


def _existing_duplicates(db: Session, kind: str, rows: list[dict]) -> list[dict]:
    errors = []
    for index, row in enumerate(rows, start=1):
        try:
            crop_id = _crop_id(db, row["crop"], index) if kind != "weather" else None
        except RowError as exc:
            errors.append({"row": exc.row, "message": exc.message})
            continue
        if kind == "prices":
            exists = db.scalar(
                select(CropPrice.id).where(
                    CropPrice.crop_id == crop_id,
                    CropPrice.market == row["market"],
                    CropPrice.region == row["region"],
                    CropPrice.date == row["date"],
                    CropPrice.source == row["source"],
                )
            )
        elif kind == "yields":
            exists = db.scalar(
                select(CropYield.id).where(
                    CropYield.crop_id == crop_id,
                    CropYield.region == row["region"],
                    CropYield.province == row["province"],
                    CropYield.date == row["date"],
                    CropYield.source == row["source"],
                )
            )
        else:
            exists = db.scalar(
                select(WeatherHistory.id).where(WeatherHistory.location == row["location"], WeatherHistory.date == row["date"])
            )
        if exists:
            errors.append({"row": index, "message": "duplicate record already stored"})
        else:
            row["crop_id"] = crop_id
    return errors


def _insert_prices(db: Session, rows: list[dict]) -> None:
    for row in rows:
        db.add(
            CropPrice(
                crop_id=row["crop_id"],
                market=row["market"],
                region=row["region"],
                price=row["price"],
                unit=row["unit"],
                date=row["date"],
                source=row["source"],
            )
        )


def _insert_yields(db: Session, rows: list[dict]) -> None:
    for row in rows:
        db.add(
            CropYield(
                crop_id=row["crop_id"],
                region=row["region"],
                province=row["province"],
                yield_value=row["yield_value"],
                yield_unit=row["yield_unit"],
                date=row["date"],
                source=row["source"],
            )
        )


def _insert_weather(db: Session, rows: list[dict]) -> None:
    for row in rows:
        db.add(
            WeatherHistory(
                location=row["location"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                date=row["date"],
                temperature_min=row["temperature_min"],
                temperature_max=row["temperature_max"],
                rainfall=row["rainfall"],
                source=row["source"],
            )
        )


def _import_document(db, job, body, source, region, crop, province, document_type, title) -> ImportJob:
    if not body.strip():
        _fail(db, job, [{"row": 0, "message": "document is empty"}])
    document = Document(
        title=title,
        source=source,
        document_type=document_type or "production_guide",
        publication_date=date.today(),
        region=region,
        province=province,
        metadata_json={"crop": crop, "import_job_id": job.id, "data_quality": "unreviewed"},
    )
    db.add(document)
    db.flush()
    pieces = chunk_text(body)
    if not pieces:
        pieces = [{"section": None, "content": body.strip()}]
    for index, piece in enumerate(pieces):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=piece["content"],
                metadata_json={
                    "crop": crop,
                    "region": region,
                    "province": province,
                    "section": piece.get("section"),
                    "embedding_status": "pending",
                },
            )
        )
    job.status = "ready"
    job.row_count = len(pieces)
    job.metadata_json = {**(job.metadata_json or {}), "document_id": document.id, "embedding_status": "pending"}
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    return job
