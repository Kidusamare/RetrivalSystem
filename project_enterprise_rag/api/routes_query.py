from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import require_api_key
from services.rag_service import plan_query_service, search_chunks_service

router = APIRouter(
    prefix="/query",
    tags=["query-compat"],
    dependencies=[Depends(require_api_key)],
)


class PlanQueryRequest(BaseModel):
    user_query: str
    mode: Optional[str] = None
    planner_backend: Optional[str] = None
    include_terms: List[str] = Field(default_factory=list)
    exclude_terms: List[str] = Field(default_factory=list)
    active_filters: List[str] = Field(default_factory=list)


class SearchQueryRequest(BaseModel):
    user_query: str
    planned_query: Optional[str] = None
    active_filters: List[str] = Field(default_factory=list)
    include_terms: List[str] = Field(default_factory=list)
    exclude_terms: List[str] = Field(default_factory=list)
    top_k: Optional[int] = None
    mode: Optional[str] = None
    sort_by: Optional[str] = None
    page: int = 1
    page_size: Optional[int] = None
    planner_backend: Optional[str] = None
    response_backend: Optional[str] = None


@router.post("/plan", deprecated=True)
def plan_query_endpoint(payload: PlanQueryRequest):
    """Compatibility wrapper for legacy /query/plan."""
    return plan_query_service(
        user_query=payload.user_query,
        mode=payload.mode,
        planner_backend=payload.planner_backend,
        include_terms=payload.include_terms,
        exclude_terms=payload.exclude_terms,
        active_filters=payload.active_filters,
    )


@router.post("/search", deprecated=True)
def search_chunks_endpoint(payload: SearchQueryRequest):
    """Compatibility wrapper for legacy /query/search."""
    return search_chunks_service(
        user_query=payload.user_query,
        planned_query=payload.planned_query,
        active_filters=payload.active_filters,
        include_terms=payload.include_terms,
        exclude_terms=payload.exclude_terms,
        top_k=payload.top_k,
        mode=payload.mode,
        sort_by=payload.sort_by,
        page=payload.page,
        page_size=payload.page_size,
        planner_backend=payload.planner_backend,
        response_backend=payload.response_backend,
    )
