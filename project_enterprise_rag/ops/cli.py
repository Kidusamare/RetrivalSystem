from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Dict, Union
from urllib.parse import urlencode

import requests

from config.settings import get_settings


TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _post(base_url: str, api_key: str, path: str, payload: dict) -> dict:
    response = requests.post(
        base_url.rstrip("/") + path,
        headers=_headers(api_key),
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    return response.json()


def _get(base_url: str, api_key: str, path: str) -> dict:
    response = requests.get(base_url.rstrip("/") + path, headers=_headers(api_key), timeout=45)
    response.raise_for_status()
    return response.json()


def _is_terminal_status(value: str) -> bool:
    return (value or "").strip().lower() in TERMINAL_JOB_STATUSES


def cmd_ingest_files(args) -> int:
    payload = {
        "file_paths": args.files,
        "options": {
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "deep_memory": bool(args.deep_memory),
            "dedupe": "sha256",
        },
    }
    out = _post(args.base_url, args.api_key, "/v1/ingestions/files", payload)
    print(json.dumps(out, indent=2))
    return 0


def cmd_sync_patentsview(args) -> int:
    payload = {
        "query": {
            "keywords": args.keywords,
            "max_records": args.max_records,
        },
        "options": {
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "deep_memory": bool(args.deep_memory),
            "dedupe": "patent_id",
        },
    }
    out = _post(args.base_url, args.api_key, "/v1/ingestions/patentsview", payload)
    print(json.dumps(out, indent=2))
    return 0


def cmd_job_status(args) -> int:
    poll_interval = max(0.2, float(args.interval))
    timeout_seconds = max(0.0, float(args.timeout))
    start = time.monotonic()

    while True:
        out = _get(args.base_url, args.api_key, f"/v1/jobs/{args.job_id}")
        status = str(out.get("status") or "").strip().lower()

        if not args.watch:
            print(json.dumps(out, indent=2))
            return 0

        print(f"[watch] job={args.job_id} status={status or 'unknown'} progress={out.get('progress')}")

        if _is_terminal_status(status):
            print(json.dumps(out, indent=2))
            if status in {"failed", "cancelled"}:
                return 1
            return 0

        if timeout_seconds > 0 and (time.monotonic() - start) >= timeout_seconds:
            print(json.dumps(out, indent=2))
            print(
                f"Timed out waiting for terminal status after {timeout_seconds:.1f}s.",
                file=sys.stderr,
            )
            return 2

        time.sleep(poll_interval)


def cmd_list_jobs(args) -> int:
    query: Dict[str, Union[int, str]] = {"limit": max(1, min(int(args.limit), 200))}
    selected_status = (args.status or "").strip().lower()
    if selected_status and selected_status != "all":
        query["status"] = selected_status

    out = _get(args.base_url, args.api_key, f"/v1/jobs?{urlencode(query)}")
    print(json.dumps(out, indent=2))
    return 0


def cmd_evaluate(args) -> int:
    # Import lazily so ops CLI commands work in minimal envs without llama_index.
    from evaluation.runner import run_precision_eval

    result = run_precision_eval(args.dataset)
    print(json.dumps(result, indent=2))
    if result["value"] < args.min_precision:
        print(
            f"Precision gate failed: {result['value']:.4f} < {args.min_precision:.4f}",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Operations CLI for Strategic IP retrieval skeleton.")
    parser.add_argument("--base-url", default=settings.ops_api_base_url)
    parser.add_argument("--api-key", default=settings.ops_api_key)

    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest-files", help="Queue local file ingestion job")
    ingest.add_argument("files", nargs="+", help="Absolute file paths")
    ingest.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    ingest.add_argument("--chunk-overlap", type=int, default=settings.chunk_overlap)
    ingest.add_argument("--deep-memory", action="store_true", help="Enable LlamaIndex deep-memory semantic chunking")
    ingest.set_defaults(func=cmd_ingest_files)

    patents = sub.add_parser("sync-patentsview", help="Queue PatentsView ingestion job")
    patents.add_argument("keywords", nargs="+", help="Keyword terms")
    patents.add_argument("--max-records", type=int, default=200)
    patents.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    patents.add_argument("--chunk-overlap", type=int, default=settings.chunk_overlap)
    patents.add_argument("--deep-memory", action="store_true", help="Enable LlamaIndex deep-memory semantic chunking")
    patents.set_defaults(func=cmd_sync_patentsview)

    status = sub.add_parser("job-status", help="Fetch job status")
    status.add_argument("job_id")
    status.add_argument("--watch", action="store_true", help="Poll until terminal job status")
    status.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds for --watch")
    status.add_argument("--timeout", type=float, default=180.0, help="Timeout in seconds for --watch (0 disables)")
    status.set_defaults(func=cmd_job_status)

    list_jobs = sub.add_parser("list-jobs", help="List recent jobs")
    list_jobs.add_argument("--status", default="all", choices=["all", "queued", "running", "succeeded", "failed", "cancelled"])
    list_jobs.add_argument("--limit", type=int, default=20)
    list_jobs.set_defaults(func=cmd_list_jobs)

    eval_cmd = sub.add_parser("evaluate", help="Run retrieval evaluation")
    eval_cmd.add_argument("--dataset", default="evaluation/gold/semiconductor_v1.yaml")
    eval_cmd.add_argument("--min-precision", type=float, default=0.9)
    eval_cmd.set_defaults(func=cmd_evaluate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
