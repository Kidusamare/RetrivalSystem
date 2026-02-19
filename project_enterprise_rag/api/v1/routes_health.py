from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from config.settings import get_settings, resolve_paths
from db.session import session_scope
from services.index_state import get_runtime_index_dir, index_dir_ready
from services.job_service import get_last_worker_heartbeat, queue_depth, worker_is_healthy
from services.metrics import render_metrics

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health/live")
def health_live():
    return {"status": "live"}


@router.get("/health/ready")
def health_ready():
    settings = resolve_paths(get_settings())

    db_ok = False
    db_error = None
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)

    runtime_index_dir = get_runtime_index_dir(settings)
    index_ok = index_dir_ready(runtime_index_dir)

    heartbeat = get_last_worker_heartbeat(settings.worker_name)
    heartbeat_iso = heartbeat.astimezone(timezone.utc).isoformat() if heartbeat else None
    worker_ok = worker_is_healthy(settings)

    ready = db_ok and worker_ok
    status = "ready" if ready else "degraded"

    return {
        "status": status,
        "checks": {
            "database": {"ok": db_ok, "error": db_error},
            "worker": {
                "ok": worker_ok,
                "worker_name": settings.worker_name,
                "last_heartbeat": heartbeat_iso,
            },
            "index": {
                "ok": index_ok,
                "path": str(runtime_index_dir),
            },
            "queue": {
                "depth": queue_depth(),
            },
        },
    }


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return render_metrics()
