#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

API_KEY="${API_KEYS:-dev-local-key}"

cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[ci] building images"
docker compose build

echo "[ci] lint + type + unit + eval"
docker compose run --rm api bash -lc "python -c 'from db.session import run_migrations; run_migrations()' && python -m compileall -q . && ruff check evaluation ops api/v1 jobs services connectors db config && python -m mypy --config-file mypy.ini && python -m unittest discover -s tests -v && python -m evaluation.runner --dataset evaluation/gold/semiconductor_v1.yaml --min-precision 0.9"

echo "[ci] starting services"
docker compose up -d api worker

echo "[ci] waiting for live endpoint"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/v1/health/live" >/dev/null; then
    break
  fi
  sleep 2
done

LIVE_STATUS=$(curl -fsS "http://127.0.0.1:8000/v1/health/live" | python -c 'import sys,json; print(json.load(sys.stdin).get("status"))')
if [[ "$LIVE_STATUS" != "live" ]]; then
  echo "[ci] live check failed"
  exit 1
fi

echo "[ci] queueing ingestion smoke job"
JOB_ID=$(curl -fsS -X POST "http://127.0.0.1:8000/v1/ingestions/files" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"file_paths":["/app/other_files/Applied Generative AI for Begineers.md"],"options":{"dedupe":"sha256","chunk_size":500,"chunk_overlap":50}}' | python -c 'import sys,json; print(json.load(sys.stdin)["job_id"])')

if [[ -z "$JOB_ID" ]]; then
  echo "[ci] no job id returned"
  exit 1
fi

echo "[ci] polling job status $JOB_ID"
JOB_STATUS="queued"
for _ in $(seq 1 40); do
  JOB_STATUS=$(curl -fsS "http://127.0.0.1:8000/v1/jobs/${JOB_ID}" -H "X-API-Key: ${API_KEY}" | python -c 'import sys,json; print(json.load(sys.stdin).get("status"))')
  if [[ "$JOB_STATUS" == "succeeded" ]]; then
    break
  fi
  if [[ "$JOB_STATUS" == "failed" ]]; then
    echo "[ci] ingestion job failed"
    exit 1
  fi
  sleep 2
done

if [[ "$JOB_STATUS" != "succeeded" ]]; then
  echo "[ci] ingestion job did not succeed in time"
  exit 1
fi

echo "[ci] running search smoke check"
SEARCH_TOTAL=$(curl -fsS -X POST "http://127.0.0.1:8000/v1/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"user_query":"semiconductor interconnect reliability","mode":"hybrid","page":1,"page_size":10}' | python -c 'import sys,json; print(json.load(sys.stdin).get("total_results", 0))')

if [[ "$SEARCH_TOTAL" -lt 0 ]]; then
  echo "[ci] invalid search response"
  exit 1
fi

echo "[ci] completed successfully"
