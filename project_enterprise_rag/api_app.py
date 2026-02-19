import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes_ingest import router as ingest_compat_router
from api.routes_query import router as query_compat_router
from api.v1.routes_health import router as health_router
from api.v1.routes_ingestions import router as ingestions_router
from api.v1.routes_jobs import router as jobs_router
from api.v1.routes_search import router as search_router
from config.settings import get_settings, resolve_paths
from db.session import run_migrations
from services.job_service import bootstrap_api_keys
from services.metrics import inc_counter, observe_duration

app = FastAPI(title="Strategic IP Retrieval API (Production Skeleton v1)")


@app.on_event("startup")
def bootstrap_runtime_state() -> None:
    settings = resolve_paths(get_settings())
    run_migrations()
    bootstrap_api_keys(settings.api_key_seed_values)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    route_token = request.url.path.strip("/").replace("/", "_") or "root"
    inc_counter(f"http_requests_total{{route='{route_token}'}}")

    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        inc_counter("http_errors_total")
        observe_duration("http_request_duration", time.perf_counter() - started)
        return JSONResponse(
            status_code=500,
            content={"error_type": "dependency_error", "message": str(exc)},
        )

    observe_duration("http_request_duration", time.perf_counter() - started)
    return response


app.include_router(health_router)
app.include_router(ingestions_router)
app.include_router(jobs_router)
app.include_router(search_router)

# Compatibility adapters kept during milestone-1 transition.
app.include_router(ingest_compat_router)
app.include_router(query_compat_router)
