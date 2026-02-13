from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from config.settings import get_settings
from ingestion.file_registry import list_registered_files
from services.rag_service import ingest_files_service

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    file_paths: List[str]


@router.post("")
def ingest_files_endpoint(payload: IngestRequest):
    return ingest_files_service(payload.file_paths)


@router.get("/status")
def ingest_status_endpoint():
    settings = get_settings()
    files = list_registered_files(settings.registry_path)
    return {
        "total_registered_files": len(files),
        "files": files,
    }

