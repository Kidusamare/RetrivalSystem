from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.rag_service import plan_query_service, search_chunks_service

router = APIRouter(prefix="/query", tags=["query"])


class PlanQueryRequest(BaseModel):
    user_query: str


class SearchQueryRequest(BaseModel):
    user_query: str
    planned_query: Optional[str] = None
    active_filters: List[str] = Field(default_factory=list)
    top_k: Optional[int] = None


@router.post("/plan")
def plan_query_endpoint(payload: PlanQueryRequest):
    return plan_query_service(payload.user_query)


@router.post("/search")
def search_chunks_endpoint(payload: SearchQueryRequest):
    return search_chunks_service(
        user_query=payload.user_query,
        planned_query=payload.planned_query,
        active_filters=payload.active_filters,
        top_k=payload.top_k,
    )

