[PLANS]
2026-02-18T22:45:41-06:00 [USER] [MILESTONE] Complete Production Skeleton v1 through Phase 7: stable `/v1` API, async jobs/worker, PatentsView + file ingestion, retrieval parity, ops UI/CLI, evaluation gate, and legacy cleanup.

[DECISIONS]
2026-02-18T20:32:30-06:00 [USER] Locked architecture: API-first `/v1`, SQLite + Alembic, async worker, API-key auth, compatibility routes retained in milestone 1, LLM features off by default.
2026-02-18T22:45:41-06:00 [CODE] [MILESTONE] Phase 6 gate uses Dockerized lint/type/unit/eval/integration checks (`ruff`, `mypy`, `unittest`, evaluation runner, compose smoke).
2026-02-18T22:45:41-06:00 [CODE] [MILESTONE] Phase 7 keeps legacy endpoints operational but OpenAPI-marked deprecated; stale legacy files removed.
2026-02-18T23:01:20-06:00 [CODE] PatentsView env vars must be explicitly mapped in `docker-compose.yml` for API/worker; `.env` alone is insufficient without container environment entries.
2026-02-19T00:02:02-06:00 [CODE] Deep Memory ingestion is opt-in via request option (`options.deep_memory`) or env default (`INGESTION_DEEP_MEMORY_ENABLED`), preserving sentence-splitter behavior by default.

[PROGRESS]
2026-02-18T22:21:30-06:00 [CODE] [MILESTONE] Phase 5 completed: Gradio internal ops panel now uses `/v1` for ingestion/status/list-jobs; CLI has `ingest-files`, `sync-patentsview`, `job-status --watch`, `list-jobs`, `evaluate`.
2026-02-18T22:45:41-06:00 [CODE] Phase 6 changes applied: added `project_enterprise_rag/mypy.ini`, added `ruff` dependency, updated `project_enterprise_rag/scripts/ci.sh` to enforce lint/type checks before tests/eval/smoke.
2026-02-18T22:45:41-06:00 [CODE] Phase 7 changes applied: deprecated compatibility decorators in `project_enterprise_rag/api/routes_query.py` and `project_enterprise_rag/api/routes_ingest.py`; removed `project_enterprise_rag/retrieval_api/requirements.txt`; updated `project_enterprise_rag/README.md` cleanup/deprecation notes.
2026-02-18T23:01:20-06:00 [CODE] Added `project_enterprise_rag/.env.example` with PatentsView/API/UI variables and updated `project_enterprise_rag/docker-compose.yml` to pass `PATENTSVIEW_*` vars into `api` and `worker` containers.
2026-02-18T23:27:11-06:00 [TOOL] Reset SQLite state by stopping `api/worker`, deleting `project_enterprise_rag/storage/state.db*`, re-running Alembic migrations, and restarting services.
2026-02-19T00:02:02-06:00 [CODE] Added LlamaIndex Deep Memory ingestion path in `ingestion/chunker.py` using `SemanticSplitterNodeParser` + `IngestionPipeline`, deep-memory metadata links, and request/config plumbing through `/v1/ingestions`, job handlers, Gradio, and ops CLI.

[DISCOVERIES]
2026-02-18T20:52:24-06:00 [TOOL] Host env lacks `fastapi`; API-route tests skip locally but run in containerized CI.
2026-02-18T22:45:41-06:00 [TOOL] Fresh dependency resolution is heavy/slow due unpinned `torch` transitive CUDA packages; cached image path is much faster for repeat CI runs.
2026-02-19T00:02:02-06:00 [TOOL] Host env also lacks `llama_index`; deep-memory tests require containerized execution for full validation.

[OUTCOMES]
2026-02-18T22:45:41-06:00 [TOOL] Full Phase 6/7 gate passed via `project_enterprise_rag/scripts/ci.sh`: lint/type/unit/evaluation/integration smoke all green; evaluation reported `precision@10 = 1.0000`.
2026-02-18T22:45:41-06:00 [TOOL] Host verification passed: `python -m unittest discover -s tests -v` returned `37` tests run with expected FastAPI-dependent skips in host env.
2026-02-18T23:01:20-06:00 [TOOL] Runtime startup confirmed: `docker compose up -d api worker` plus `strategic-ip-ui` container running; health checks succeeded at `http://127.0.0.1:8000/v1/health/live` and `http://127.0.0.1:7860/`.
2026-02-18T23:27:11-06:00 [TOOL] Post-reset runtime healthy: API liveness returned live on `http://127.0.0.1:8000/v1/health/live`; UI remained reachable on `http://127.0.0.1:7860/`.
2026-02-19T00:02:02-06:00 [TOOL] Deep-memory change-set validated in container: `ruff check` clean and `python -m unittest discover -s tests -v` passed `43/43`, including new deep-memory ingestion and API/CLI contract tests.
