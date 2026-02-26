[PLANS]
2026-02-18T22:45:41-06:00 [USER] [MILESTONE] Complete Production Skeleton v1 through Phase 7: stable `/v1` API, async jobs/worker, PatentsView + file ingestion, retrieval parity, ops UI/CLI, evaluation gate, and legacy cleanup.

[DECISIONS]
2026-02-18T20:32:30-06:00 [USER] Locked architecture: API-first `/v1`, SQLite + Alembic, async worker, API-key auth, compatibility routes retained in milestone 1, LLM features off by default.
2026-02-18T22:45:41-06:00 [CODE] [MILESTONE] Phase 6 gate uses Dockerized lint/type/unit/eval/integration checks (`ruff`, `mypy`, `unittest`, evaluation runner, compose smoke).
2026-02-18T22:45:41-06:00 [CODE] [MILESTONE] Phase 7 keeps legacy endpoints operational but OpenAPI-marked deprecated; stale legacy files removed.
2026-02-18T23:01:20-06:00 [CODE] PatentsView env vars must be explicitly mapped in `docker-compose.yml` for API/worker; `.env` alone is insufficient without container environment entries.
2026-02-19T00:02:02-06:00 [CODE] Deep Memory ingestion is opt-in via request option (`options.deep_memory`) or env default (`INGESTION_DEEP_MEMORY_ENABLED`), preserving sentence-splitter behavior by default.
2026-02-26T17:35:26-06:00 [USER] Requested replacement of existing dataset docs with a broad hardware corpus (semiconductors, motherboards, GPUs, TPUs) and asked for local-LLM test cases.
2026-02-26T17:39:52-06:00 [USER] Requested code prep only for GPU-server execution and a dedicated Markdown test plan for local-LLM planner/response validation.
2026-02-26T17:44:39-06:00 [USER] Requested pre-push dead-code/dead-folder cleanup across the repo before publishing to GitHub.

[PROGRESS]
2026-02-18T22:21:30-06:00 [CODE] [MILESTONE] Phase 5 completed: Gradio internal ops panel now uses `/v1` for ingestion/status/list-jobs; CLI has `ingest-files`, `sync-patentsview`, `job-status --watch`, `list-jobs`, `evaluate`.
2026-02-18T22:45:41-06:00 [CODE] Phase 6 changes applied: added `project_enterprise_rag/mypy.ini`, added `ruff` dependency, updated `project_enterprise_rag/scripts/ci.sh` to enforce lint/type checks before tests/eval/smoke.
2026-02-18T22:45:41-06:00 [CODE] Phase 7 changes applied: deprecated compatibility decorators in `project_enterprise_rag/api/routes_query.py` and `project_enterprise_rag/api/routes_ingest.py`; removed `project_enterprise_rag/retrieval_api/requirements.txt`; updated `project_enterprise_rag/README.md` cleanup/deprecation notes.
2026-02-18T23:01:20-06:00 [CODE] Added `project_enterprise_rag/.env.example` with PatentsView/API/UI variables and updated `project_enterprise_rag/docker-compose.yml` to pass `PATENTSVIEW_*` vars into `api` and `worker` containers.
2026-02-18T23:27:11-06:00 [TOOL] Reset SQLite state by stopping `api/worker`, deleting `project_enterprise_rag/storage/state.db*`, re-running Alembic migrations, and restarting services.
2026-02-19T00:02:02-06:00 [CODE] Added LlamaIndex Deep Memory ingestion path in `ingestion/chunker.py` using `SemanticSplitterNodeParser` + `IngestionPipeline`, deep-memory metadata links, and request/config plumbing through `/v1/ingestions`, job handlers, Gradio, and ops CLI.
2026-02-26T17:35:26-06:00 [CODE] Replaced `project_enterprise_rag/datasets/semiconductor_ip_demo/docs` with a refreshed 64-document hardware dataset and regenerated `manifest.json`, `raw/records.json`, and `raw/curated_filter_options.json`.
2026-02-26T17:35:26-06:00 [CODE] Added local-LLM validation assets: `datasets/semiconductor_ip_demo/test_cases/local_llm_cases.json`, `scripts/run_local_llm_cases.py`, and README instructions for ingesting the new corpus and running planner/response smoke cases.
2026-02-26T17:39:52-06:00 [CODE] Added GPU-ready LLM runtime wiring in `project_enterprise_rag/docker-compose.yml` (`PLANNER_BACKEND`, `RESPONSE_BACKEND`, `OLLAMA_*`, host-gateway mapping) and updated `.env.example` defaults for local LLM execution.
2026-02-26T17:39:52-06:00 [CODE] Added `project_enterprise_rag/TEST_LOCAL_LLM_GPU_PLAN.md` with preflight, setup, ingestion, automated case execution, API spot checks, pass/fail gates, and troubleshooting steps.
2026-02-26T17:44:39-06:00 [CODE] Removed additional dead artifacts before push: `project_enterprise_rag/llm_chain/`, `project_enterprise_rag/store/`, `project_enterprise_rag/embeddings/`, `project_enterprise_rag/rag/`, `project_enterprise_rag/screenshots/`, `project_enterprise_rag/PLAN_ENTERPRISE_RAG_DEMO.md`, and `project_enterprise_rag/scripts/download_semiconductor_dataset.py`; also removed empty legacy `project_enterprise_rag/retrieval_api/` directory.

[DISCOVERIES]
2026-02-18T20:52:24-06:00 [TOOL] Host env lacks `fastapi`; API-route tests skip locally but run in containerized CI.
2026-02-18T22:45:41-06:00 [TOOL] Fresh dependency resolution is heavy/slow due unpinned `torch` transitive CUDA packages; cached image path is much faster for repeat CI runs.
2026-02-19T00:02:02-06:00 [TOOL] Host env also lacks `llama_index`; deep-memory tests require containerized execution for full validation.
2026-02-26T17:44:39-06:00 [TOOL] Residual mentions of legacy files are intentionally kept only in `project_enterprise_rag/README.md` deprecation/cleanup notes; no live code imports reference removed modules.

[OUTCOMES]
2026-02-18T22:45:41-06:00 [TOOL] Full Phase 6/7 gate passed via `project_enterprise_rag/scripts/ci.sh`: lint/type/unit/evaluation/integration smoke all green; evaluation reported `precision@10 = 1.0000`.
2026-02-18T22:45:41-06:00 [TOOL] Host verification passed: `python -m unittest discover -s tests -v` returned `37` tests run with expected FastAPI-dependent skips in host env.
2026-02-18T23:01:20-06:00 [TOOL] Runtime startup confirmed: `docker compose up -d api worker` plus `strategic-ip-ui` container running; health checks succeeded at `http://127.0.0.1:8000/v1/health/live` and `http://127.0.0.1:7860/`.
2026-02-18T23:27:11-06:00 [TOOL] Post-reset runtime healthy: API liveness returned live on `http://127.0.0.1:8000/v1/health/live`; UI remained reachable on `http://127.0.0.1:7860/`.
2026-02-19T00:02:02-06:00 [TOOL] Deep-memory change-set validated in container: `ruff check` clean and `python -m unittest discover -s tests -v` passed `43/43`, including new deep-memory ingestion and API/CLI contract tests.
2026-02-26T17:35:26-06:00 [TOOL] Dataset refresh validation passed: new corpus count matched metadata (`docs=64`, `records=64`) and local-LLM case file loaded with two runnable scenarios; `scripts/run_local_llm_cases.py --help` and compile check succeeded.
2026-02-26T17:39:52-06:00 [TOOL] Local prep validation passed in current environment: API liveness healthy, refreshed dataset ingestion succeeded (`64` files, `676` chunks), and both automated local-LLM cases passed via `scripts/run_local_llm_cases.py`.
2026-02-26T17:44:39-06:00 [TOOL] Post-cleanup verification passed in container: `docker compose run --rm api python -m unittest discover -s tests -v` completed `43/43` tests with `OK`.
