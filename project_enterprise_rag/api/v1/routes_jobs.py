from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth import require_api_key
from services.job_service import get_job, list_jobs

router = APIRouter(prefix="/v1/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])
HTTP_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY)


@router.get("")
def list_jobs_endpoint(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        return {"jobs": list_jobs(status=status_filter, limit=limit)}
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTP_422,
            detail={"error_type": "validation_error", "message": str(exc)},
        ) from exc


@router.get("/{job_id}")
def get_job_endpoint(job_id: str):
    row = get_job(job_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_type": "validation_error", "message": f"Job not found: {job_id}"},
        )
    return row
