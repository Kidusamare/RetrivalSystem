from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import require_api_key
from config.settings import get_settings
from ingestion.file_registry import list_registered_files
from services.job_service import enqueue_job, queue_depth

router = APIRouter(
    prefix="/ingest",
    tags=["ingest-compat"],
    dependencies=[Depends(require_api_key)],
)


class IngestRequest(BaseModel):
    file_paths: List[str]


@router.post("", deprecated=True)
def ingest_files_endpoint(payload: IngestRequest):
    # Compatibility adapter now queues v1 ingestion jobs.
    queued = enqueue_job(
        "local_files_ingest",
        {"file_paths": payload.file_paths, "options": {}},
    )
    return {
        "job_id": queued["id"],
        "status": queued["status"],
        "message": "Ingestion job queued.",
        "ingested_files_count": 0,
        "chunks_added": 0,
    }


@router.get("/status", deprecated=True)
def ingest_status_endpoint():
    settings = get_settings()
    files = list_registered_files(settings.registry_path)
    return {
        "total_registered_files": len(files),
        "files": files,
        "queue_depth": queue_depth(),
    }
