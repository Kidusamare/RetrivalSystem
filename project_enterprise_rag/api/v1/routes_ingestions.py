from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import require_api_key
from services.job_service import enqueue_job

router = APIRouter(prefix="/v1/ingestions", tags=["ingestions"], dependencies=[Depends(require_api_key)])


class FileIngestionOptions(BaseModel):
    chunk_size: Optional[int] = Field(default=None, ge=1)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    deep_memory: Optional[bool] = None
    dedupe: Literal["sha256"] = "sha256"


class PatentIngestionOptions(BaseModel):
    chunk_size: Optional[int] = Field(default=None, ge=1)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    deep_memory: Optional[bool] = None
    dedupe: Literal["patent_id"] = "patent_id"


class FileIngestionRequest(BaseModel):
    file_paths: List[str] = Field(default_factory=list)
    options: FileIngestionOptions = Field(default_factory=FileIngestionOptions)


class PatentQuery(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    max_records: int = Field(default=200, ge=1, le=5000)


class PatentIngestionRequest(BaseModel):
    query: PatentQuery
    options: PatentIngestionOptions = Field(default_factory=PatentIngestionOptions)


def _asdict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@router.post("/files")
def enqueue_file_ingestion(payload: FileIngestionRequest):
    row = enqueue_job(
        "local_files_ingest",
        {
            "file_paths": payload.file_paths,
            "options": _asdict(payload.options),
        },
    )
    return {
        "job_id": row["id"],
        "status": row["status"],
        "source_type": "local_files",
    }


@router.post("/patentsview")
def enqueue_patentsview_ingestion(payload: PatentIngestionRequest):
    row = enqueue_job(
        "patentsview_sync",
        {
            "query": _asdict(payload.query),
            "options": _asdict(payload.options),
        },
    )
    return {
        "job_id": row["id"],
        "status": row["status"],
        "source_type": "patentsview",
    }
