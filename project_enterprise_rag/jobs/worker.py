from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from config.settings import get_settings, resolve_paths
from db.session import run_migrations
from jobs.handlers.files import handle_local_file_ingestion
from jobs.handlers.patentsview import handle_patentsview_sync
from services.job_service import (
    bootstrap_api_keys,
    claim_next_job,
    mark_job_failed,
    mark_job_succeeded,
    record_worker_heartbeat,
)


def _write_heartbeat_file(path: Path, worker_name: str) -> None:
    payload = {"worker": worker_name, "ts": time.time()}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _heartbeat_loop(*, worker_name: str, heartbeat_file: Path, poll_seconds: int, stop_signal: threading.Event) -> None:
    interval = max(1, int(poll_seconds))
    while not stop_signal.is_set():
        record_worker_heartbeat(worker_name)
        _write_heartbeat_file(heartbeat_file, worker_name)
        stop_signal.wait(interval)


def main() -> None:
    settings = resolve_paths(get_settings())

    run_migrations()
    bootstrap_api_keys(settings.api_key_seed_values)

    handlers = {
        "local_files_ingest": handle_local_file_ingestion,
        "patentsview_sync": handle_patentsview_sync,
    }

    stop_signal = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        kwargs={
            "worker_name": settings.worker_name,
            "heartbeat_file": settings.worker_heartbeat_file,
            "poll_seconds": settings.worker_poll_seconds,
            "stop_signal": stop_signal,
        },
        daemon=True,
    )
    heartbeat_thread.start()

    try:
        while True:
            job = claim_next_job(settings.worker_name)
            if job is None:
                time.sleep(settings.worker_poll_seconds)
                continue

            handler = handlers.get(job.job_type)
            if handler is None:
                mark_job_failed(job.id, f"Unsupported job type: {job.job_type}")
                continue

            try:
                summary = handler(job.id, job.payload_json or {})
                mark_job_succeeded(job.id, summary)
            except Exception as exc:  # noqa: BLE001
                mark_job_failed(job.id, str(exc))
    finally:
        stop_signal.set()
        heartbeat_thread.join(timeout=2)


if __name__ == "__main__":
    main()
