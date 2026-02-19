# Strategic IP Retrieval Platform (Production Skeleton v1)

This module is now an **API-first, reliability-focused skeleton** for Strategic IP retrieval.

## What This Delivers
- Versioned API surface under `/v1/*`.
- API key auth (`X-API-Key`) for non-health routes.
- Async ingestion jobs with a dedicated worker process.
- SQLite operational state (`storage/state.db`) with Alembic migrations.
- Atomic index staging/activation flow for safer ingestion updates.
- Compatibility routes (`/query/*`, `/ingest*`) preserved during transition.
- Internal Gradio ops console that talks to the `/v1` API.
- Evaluation runner for `Precision@10` on curated semiconductor gold set.
- Dockerized quality gate covering lint, typecheck, unit, integration smoke, and evaluation.

## Runtime Architecture
- `api` service: FastAPI app (`api_app.py`).
- `worker` service: background queue processor (`python -m jobs.worker`).
- shared storage: SQLite state + active/staging index dirs under `storage/`.

## Key Endpoints
### Health and Metrics
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /v1/metrics`

### Ingestion and Jobs
- `POST /v1/ingestions/files`
- `POST /v1/ingestions/patentsview`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`

File ingestion defaults:
- `options.dedupe = "sha256"`
- `options.deep_memory = null` (falls back to `INGESTION_DEEP_MEMORY_ENABLED`)

PatentsView ingestion defaults:
- `options.dedupe = "patent_id"`
- `options.deep_memory = null` (falls back to `INGESTION_DEEP_MEMORY_ENABLED`)
- retries from `PATENTSVIEW_RETRIES` (default `3`)

### Search
- `POST /v1/search/plan`
- `POST /v1/search`

## Compatibility Endpoints (Deprecated but active)
- `POST /query/plan`
- `POST /query/search`
- `POST /ingest`
- `GET /ingest/status`

These compatibility operations are explicitly marked `deprecated: true` in OpenAPI and remain fully functional during milestone 1.

## Auth
Set API keys via `API_KEYS` env var (comma-separated).

Example:
```bash
export API_KEYS="dev-local-key"
```

All non-health endpoints require:
```http
X-API-Key: dev-local-key
```

## PatentsView Runtime Controls
- `PATENTSVIEW_API_URL` (default `https://search.patentsview.org/api/v1/patent/`)
- `PATENTSVIEW_TIMEOUT_SECONDS` (default `45`)
- `PATENTSVIEW_RETRIES` (default `3`)
- `PATENTSVIEW_API_KEY` (optional)

## Deep Memory Ingestion Controls
- `INGESTION_DEEP_MEMORY_ENABLED` (default `false`)
- `DEEP_MEMORY_BUFFER_SIZE` (default `1`)
- `DEEP_MEMORY_BREAKPOINT_PERCENTILE` (default `95`)

When deep memory is enabled, ingestion uses LlamaIndex semantic chunking (`SemanticSplitterNodeParser` + `IngestionPipeline`) and writes deep-memory linkage metadata into chunk metadata.

PatentsView job summaries include:
- connector request metadata (`base_url`, `keywords`, `max_records`, `timeout_seconds`, `retries`, `dedupe`)
- ingest summary (`fetched_records`, `new_records`, `already_indexed_records`)

## Run (Docker Compose)
```bash
cd project_enterprise_rag
docker compose up --build api worker
```

API docs: `http://localhost:8000/docs`

## Internal Ops UI (Gradio)
In a separate terminal:
```bash
cd project_enterprise_rag
export OPS_API_BASE_URL="http://127.0.0.1:8000"
export OPS_API_KEY="dev-local-key"
python app.py
```

UI URL: `http://localhost:7860`

UI operations include:
- queue file ingestion jobs
- queue PatentsView sync jobs
- toggle LlamaIndex deep-memory semantic chunking per ingestion job
- refresh a specific job status by `job_id`
- list recent jobs with status filters
- run plan/search workflows through `/v1/search/*`

## DB Migrations
```bash
cd project_enterprise_rag
alembic upgrade head
```

## Ops CLI
```bash
cd project_enterprise_rag
python -m ops.cli ingest-files /abs/path/file1.pdf /abs/path/file2.md
python -m ops.cli ingest-files /abs/path/file1.pdf --deep-memory
python -m ops.cli sync-patentsview semiconductor interconnect --max-records 200
python -m ops.cli sync-patentsview semiconductor interconnect --max-records 200 --deep-memory
python -m ops.cli job-status job_xxx
python -m ops.cli job-status job_xxx --watch --interval 2 --timeout 180
python -m ops.cli list-jobs --status running --limit 20
python -m ops.cli evaluate --dataset evaluation/gold/semiconductor_v1.yaml --min-precision 0.9
```

## Evaluation
Gold set file:
- `evaluation/gold/semiconductor_v1.yaml`

Run:
```bash
python -m evaluation.runner --dataset evaluation/gold/semiconductor_v1.yaml --min-precision 0.9
```

Current gate target:
- `Precision@10 >= 0.9`

## CI Gate
```bash
cd project_enterprise_rag
./scripts/ci.sh
```

This executes containerized:
- lint: `ruff check evaluation ops api/v1 jobs services connectors db config`
- typecheck: `mypy --config-file mypy.ini`
- tests: `python -m unittest discover -s tests -v`
- evaluation: `python -m evaluation.runner --dataset evaluation/gold/semiconductor_v1.yaml --min-precision 0.9`
- integration smoke: compose startup + ingest job + search call

## Legacy Cleanup (Phase 7)
- Removed stale files:
  - `frontend/streamlit_app.py`
  - `retrieval_api/app.py`
  - `rag/test_query.py`
  - `retrieval_api/requirements.txt`
- Kept legacy API route compatibility through adapters in `api/routes_query.py` and `api/routes_ingest.py` with deprecation markers.
