from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func, select, update

from config.settings import LocalSettings, get_settings, resolve_paths
from db.models import APIKey, Chunk, Document, EvalRun, IndexGeneration, JOB_STATUSES, Job, JobEvent, utc_now
from db.session import session_scope
from services.metrics import inc_counter
from services.security import hash_api_key

SUPPORTED_JOB_TYPES = frozenset({"local_files_ingest", "patentsview_sync"})


def _normalize_job_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    cleaned = status.strip().lower()
    if not cleaned:
        return None
    if cleaned not in JOB_STATUSES:
        allowed = ", ".join(JOB_STATUSES)
        raise ValueError(f"Unsupported job status '{status}'. Allowed values: {allowed}")
    return cleaned


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _job_to_dict(job: Job) -> Dict[str, Any]:
    return {
        "id": job.id,
        "type": job.job_type,
        "status": job.status,
        "progress": float(job.progress or 0.0),
        "result_summary": job.result_summary_json or {},
        "error": job.error,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "updated_at": _iso(job.updated_at),
    }


def enqueue_job(job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned_job_type = (job_type or "").strip()
    if cleaned_job_type not in SUPPORTED_JOB_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_JOB_TYPES))
        raise ValueError(f"Unsupported job type '{job_type}'. Allowed values: {allowed}")

    now = utc_now()
    job = Job(
        id=f"job_{uuid.uuid4().hex[:16]}",
        job_type=cleaned_job_type,
        status="queued",
        payload_json=payload,
        progress=0.0,
        created_at=now,
        updated_at=now,
    )

    with session_scope() as session:
        session.add(job)
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="queued",
                message=f"Job queued: {cleaned_job_type}",
                metadata_json={"job_type": cleaned_job_type},
            )
        )

    inc_counter("jobs_queued_total")
    return _job_to_dict(job)


def claim_next_job(worker_name: str) -> Optional[Job]:
    cleaned_worker_name = (worker_name or "").strip() or "worker"

    with session_scope() as session:
        while True:
            candidate_job_id = session.execute(
                select(Job.id)
                .where(Job.status == "queued")
                .order_by(Job.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()

            if candidate_job_id is None:
                return None

            claimed_at = utc_now()
            claim_update = session.execute(
                update(Job)
                .where(Job.id == candidate_job_id, Job.status == "queued")
                .values(
                    status="running",
                    started_at=claimed_at,
                    updated_at=claimed_at,
                )
            )

            if int(claim_update.rowcount or 0) != 1:
                # Another worker claimed it first; retry with next queued row.
                continue

            session.add(
                JobEvent(
                    job_id=candidate_job_id,
                    event_type="running",
                    message=f"Claimed by {cleaned_worker_name}",
                    metadata_json={"worker_name": cleaned_worker_name},
                )
            )

            row = session.get(Job, candidate_job_id)
            if row is None:
                return None
            session.flush()
            session.expunge(row)
            return row


def update_job_progress(job_id: str, progress: float, message: str = "") -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            return
        job.progress = max(0.0, min(1.0, float(progress)))
        job.updated_at = utc_now()
        if message:
            session.add(JobEvent(job_id=job_id, event_type="progress", message=message, metadata_json={"progress": job.progress}))


def mark_job_succeeded(job_id: str, result_summary: Dict[str, Any]) -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            return
        job.status = "succeeded"
        job.progress = 1.0
        job.result_summary_json = result_summary
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        session.add(JobEvent(job_id=job_id, event_type="succeeded", message="Job completed", metadata_json=result_summary))
    inc_counter("jobs_succeeded_total")


def mark_job_failed(job_id: str, error_message: str) -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            return
        job.status = "failed"
        job.error = error_message
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        session.add(JobEvent(job_id=job_id, event_type="failed", message=error_message, metadata_json={}))
    inc_counter("jobs_failed_total")


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(Job, job_id)
        if row is None:
            return None
        return _job_to_dict(row)


def list_jobs(*, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    status_filter = _normalize_job_status(status)

    with session_scope() as session:
        stmt = select(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 200)))
        if status_filter:
            stmt = stmt.where(Job.status == status_filter)
        rows = session.execute(stmt).scalars().all()
        return [_job_to_dict(row) for row in rows]


def queue_depth() -> int:
    with session_scope() as session:
        value = session.execute(select(func.count(Job.id)).where(Job.status == "queued")).scalar_one()
        return int(value or 0)


def record_worker_heartbeat(worker_name: str) -> None:
    with session_scope() as session:
        session.add(
            JobEvent(
                job_id=None,
                event_type="worker_heartbeat",
                message=f"heartbeat:{worker_name}",
                metadata_json={"worker_name": worker_name},
            )
        )


def get_last_worker_heartbeat(worker_name: Optional[str] = None) -> Optional[datetime]:
    with session_scope() as session:
        stmt = (
            select(JobEvent)
            .where(JobEvent.event_type == "worker_heartbeat")
            .order_by(JobEvent.created_at.desc())
            .limit(50)
        )
        events = session.execute(stmt).scalars().all()
        for event in events:
            if worker_name and event.metadata_json.get("worker_name") != worker_name:
                continue
            return event.created_at
        return None


def worker_is_healthy(settings: Optional[LocalSettings] = None) -> bool:
    cfg = resolve_paths(settings or get_settings())
    heartbeat = get_last_worker_heartbeat(cfg.worker_name)
    if heartbeat is None:
        return False
    max_age = timedelta(seconds=cfg.worker_heartbeat_ttl_seconds)
    return utc_now() - heartbeat <= max_age


def bootstrap_api_keys(raw_keys: Iterable[str]) -> int:
    inserted = 0
    now = utc_now()
    with session_scope() as session:
        existing_hashes = {
            row.key_hash for row in session.execute(select(APIKey).where(APIKey.is_active == True)).scalars().all()  # noqa: E712
        }
        for raw_key in raw_keys:
            cleaned = (raw_key or "").strip()
            if not cleaned:
                continue
            key_hash = hash_api_key(cleaned)
            if key_hash in existing_hashes:
                continue
            record = APIKey(name=f"seed-{key_hash[:12]}", key_hash=key_hash, is_active=True, created_at=now)
            session.add(record)
            existing_hashes.add(key_hash)
            inserted += 1
    return inserted


def verify_api_key(raw_key: str) -> bool:
    hashed = hash_api_key(raw_key)
    with session_scope() as session:
        row = session.execute(
            select(APIKey).where(APIKey.key_hash == hashed, APIKey.is_active == True)  # noqa: E712
        ).scalar_one_or_none()
        if row is None:
            return False
        row.last_used_at = utc_now()
        return True


def record_index_generation(generation_id: str, path: str, status: str) -> None:
    with session_scope() as session:
        session.add(
            IndexGeneration(
                generation_id=generation_id,
                path=path,
                status=status,
                created_at=utc_now(),
                activated_at=utc_now() if status == "active" else None,
            )
        )


def upsert_documents_and_chunks(*, documents: List[Dict[str, Any]], chunks: List[Dict[str, Any]]) -> None:
    with session_scope() as session:
        document_id_aliases: Dict[str, str] = {}

        for doc in documents:
            source_doc_id = str(doc["id"])
            doc_key = doc["doc_key"]
            existing = session.execute(select(Document).where(Document.doc_key == doc_key)).scalar_one_or_none()
            if existing is None and doc.get("patent_id"):
                existing = session.execute(
                    select(Document).where(Document.patent_id == str(doc.get("patent_id")))
                ).scalar_one_or_none()
            if existing is None and doc.get("sha256"):
                existing = session.execute(
                    select(Document).where(Document.sha256 == str(doc.get("sha256")))
                ).scalar_one_or_none()

            if existing:
                existing.source_type = doc["source_type"]
                existing.doc_key = doc_key
                existing.doc_id = doc["doc_id"]
                existing.file_name = doc["file_name"]
                existing.source_path = doc["source_path"]
                existing.metadata_json = doc.get("metadata_json", {})
                existing.sha256 = doc.get("sha256")
                existing.patent_id = doc.get("patent_id")
                document_id_aliases[source_doc_id] = str(existing.id)
                document_id_aliases[str(doc.get("doc_id") or source_doc_id)] = str(existing.id)
                continue

            session.add(
                Document(
                    id=source_doc_id,
                    source_type=doc["source_type"],
                    doc_key=doc_key,
                    doc_id=doc["doc_id"],
                    file_name=doc["file_name"],
                    source_path=doc["source_path"],
                    sha256=doc.get("sha256"),
                    patent_id=doc.get("patent_id"),
                    metadata_json=doc.get("metadata_json", {}),
                    created_at=utc_now(),
                )
            )
            document_id_aliases[source_doc_id] = source_doc_id
            document_id_aliases[str(doc.get("doc_id") or source_doc_id)] = source_doc_id

        # Ensure document rows are present before chunk inserts with FK references.
        session.flush()
        document_ids = {row[0] for row in session.execute(select(Document.id)).all()}

        for chunk in chunks:
            raw_document_id = str(chunk["document_id"])
            document_id = document_id_aliases.get(raw_document_id, raw_document_id)
            if document_id not in document_ids:
                session.add(
                    Document(
                        id=document_id,
                        source_type="unknown",
                        doc_key=f"doc:{document_id}",
                        doc_id=document_id,
                        file_name=f"{document_id}.txt",
                        source_path=f"unknown://{document_id}",
                        sha256=None,
                        patent_id=None,
                        metadata_json={"autocreated": True},
                        created_at=utc_now(),
                    )
                )
                session.flush()
                document_ids.add(document_id)

            existing = session.execute(select(Chunk).where(Chunk.chunk_id == chunk["chunk_id"])).scalar_one_or_none()
            if existing:
                continue

            raw_chunk_doc_id = str(chunk.get("doc_id") or raw_document_id)
            chunk_doc_id = document_id_aliases.get(raw_chunk_doc_id, document_id)
            session.add(
                Chunk(
                    chunk_id=chunk["chunk_id"],
                    document_id=document_id,
                    doc_id=chunk_doc_id,
                    content=chunk["content"],
                    metadata_json=chunk.get("metadata_json", {}),
                    created_at=utc_now(),
                )
            )


def record_eval_run(dataset_name: str, metric_name: str, metric_value: float, details: Dict[str, Any]) -> str:
    eval_id = f"eval_{uuid.uuid4().hex[:16]}"
    with session_scope() as session:
        session.add(
            EvalRun(
                id=eval_id,
                dataset_name=dataset_name,
                metric_name=metric_name,
                metric_value=float(metric_value),
                details_json=details,
                created_at=utc_now(),
            )
        )
    return eval_id
