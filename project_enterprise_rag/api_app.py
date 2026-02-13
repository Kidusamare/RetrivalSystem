from fastapi import FastAPI

from api.routes_ingest import router as ingest_router
from api.routes_query import router as query_router

app = FastAPI(title="Enterprise RAG API (Local Retrieval)")
app.include_router(ingest_router)
app.include_router(query_router)

