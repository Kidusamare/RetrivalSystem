# Enterprise RAG Demo (Local + No Cost)

This project is now a **fully local, retrieval-only enterprise RAG demo**.

## What It Demonstrates
- Multi-file ingestion with local file registry and deduplication.
- Deterministic query planning (`user query -> planned query + keywords`) with editable query input.
- Ranked chunk retrieval with highlighted terms in output.
- Top-k filter suggestion from retrieved chunks for iterative narrowing.
- No paid APIs in the demo path.

## Architecture Modules
- `config/` local settings and path resolution.
- `ingestion/` registry, parsing, chunking, and index persistence.
- `retrieval/` planner, retriever, highlighter, formatter, filter suggester.
- `services/` orchestration layer used by UI and API.
- `api/` ingest and query route modules.
- `frontend/gradio_app.py` interactive demo UI.

## Run (UI)
```bash
cd project_enterprise_rag
docker build -t enterprise-rag:local .
docker run --rm -p 7860:7860 enterprise-rag:local
```
Open `http://localhost:7860`.

## Run (API)
```bash
cd project_enterprise_rag
docker build -t enterprise-rag:local .
docker run --rm -p 8000:8000 enterprise-rag:local uvicorn api_app:app --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

## Key Endpoints
- `POST /ingest` with JSON: `{"file_paths": ["/app/path/to/file.txt"]}`
- `GET /ingest/status`
- `POST /query/plan` with JSON: `{"user_query": "your question"}`
- `POST /query/search` with JSON:
  - `user_query` (required)
  - `planned_query` (optional)
  - `active_filters` (optional list)
  - `top_k` (optional int)

## Scripts
- `scripts/run_local_demo.sh` starts the Gradio app.
- `scripts/reindex_local.py` reindexes files and supports reset flags.

## Testing
Run unit tests in container:
```bash
cd project_enterprise_rag
docker build -t enterprise-rag:test .
docker run --rm enterprise-rag:test python -m unittest discover -s tests -v
```
