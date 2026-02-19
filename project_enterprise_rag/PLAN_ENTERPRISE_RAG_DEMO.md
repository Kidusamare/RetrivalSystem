# Enterprise RAG Demo Plan

## Goal
Build a modular, demo-ready enterprise RAG system that supports:
1. Multi-file ingestion and indexing.
2. Editable retrieval queries generated from user query.
3. Prettier retrieved chunk rendering with query/document keyword highlighting.
4. Suggested keyword filters (top-k facets) to narrow retrieval.

## Hard Constraints (Local + Zero Cost)
- Run fully local for demo execution.
- Use no paid API calls.
- Do not use OpenAI, Groq, Mixedbread API, or LlamaParse cloud in the demo path.
- Keep retrieval-only output (no LLM-generated final answer).
- Store index and metadata only in local filesystem.

## Scope
- Focus on retrieval quality, explainability, and demo UX.
- Keep code modular and avoid a single monolithic file.
- Preserve current stack: Python, LlamaIndex, Gradio/FastAPI, local/persistent storage.
- Prefer local embeddings (`sentence-transformers` via HuggingFace) and deterministic logic.

## Current State (Observed)
- Retrieval-only chunk output is already implemented in `project_enterprise_rag/rag/query_engine.py`.
- UI shows pretty chunk cards with basic highlighting in `project_enterprise_rag/app.py`.
- Ingestion is still mostly single-flow and not yet first-class multi-file with registry controls.
- Query planning edit loop and top-k filter recommendation UX are not yet implemented.

## Target Architecture
Create the following module groups:

```text
project_enterprise_rag/
  config/
    settings.py
  ingestion/
    file_registry.py
    parser.py
    chunker.py
    index_builder.py
  retrieval/
    query_planner.py
    retriever.py
    filter_suggester.py
    highlighter.py
    formatter.py
  services/
    rag_service.py
  api/
    routes_ingest.py
    routes_query.py
  frontend/
    gradio_app.py
  tests/
    test_ingestion_registry.py
    test_query_planner.py
    test_filter_suggester.py
    test_highlighter.py
  scripts/
    run_local_demo.sh
    reindex_local.py
```

## Planned Additions: Files, Functions, and Reason

| File to Add | Planned Functions | Reason (concise) |
|---|---|---|
| `project_enterprise_rag/config/settings.py` | `get_settings()`, `resolve_paths()` | Centralize local-only paths and feature flags. |
| `project_enterprise_rag/ingestion/file_registry.py` | `load_registry()`, `save_registry()`, `register_files()`, `list_registered_files()` | Track multi-file ingestion state and deduplicate files. |
| `project_enterprise_rag/ingestion/parser.py` | `validate_supported_file()`, `load_documents_from_files()` | Standardize local document loading and type checks. |
| `project_enterprise_rag/ingestion/chunker.py` | `chunk_documents()`, `attach_chunk_metadata()` | Build consistent chunks and metadata for retrieval. |
| `project_enterprise_rag/ingestion/index_builder.py` | `load_or_create_index()`, `upsert_chunks()`, `persist_index()` | Incrementally update and persist vector index locally. |
| `project_enterprise_rag/retrieval/query_planner.py` | `extract_keywords()`, `build_planned_query()`, `plan_query()` | Deterministic query planning that user can edit. |
| `project_enterprise_rag/retrieval/retriever.py` | `retrieve_chunks()`, `apply_active_filters()` | Separate retrieval orchestration from UI/API concerns. |
| `project_enterprise_rag/retrieval/filter_suggester.py` | `suggest_filters()`, `normalize_filter_terms()` | Produce top-k narrowing terms from retrieved chunks. |
| `project_enterprise_rag/retrieval/highlighter.py` | `build_highlight_terms()`, `highlight_text()` | Keep highlighting reusable and testable. |
| `project_enterprise_rag/retrieval/formatter.py` | `format_chunk_card()`, `format_api_chunk()` | Keep pretty rendering and API payload formatting consistent. |
| `project_enterprise_rag/services/rag_service.py` | `ingest_files_service()`, `plan_query_service()`, `search_chunks_service()` | Provide one application service layer used by UI and API. |
| `project_enterprise_rag/api/routes_ingest.py` | `ingest_files_endpoint()`, `ingest_status_endpoint()` | Expose ingestion controls for demo and automation. |
| `project_enterprise_rag/api/routes_query.py` | `plan_query_endpoint()`, `search_chunks_endpoint()` | Expose plan/edit/retrieve flow as stable API contracts. |
| `project_enterprise_rag/frontend/gradio_app.py` | `build_ui()`, `on_ingest_files()`, `on_plan_query()`, `on_search()`, `on_apply_filter()` | Implement interactive demo loop in modular handlers. |
| `project_enterprise_rag/tests/test_ingestion_registry.py` | `test_register_files_deduplicates_by_hash()` | Prevent duplicate file/index state regressions. |
| `project_enterprise_rag/tests/test_query_planner.py` | `test_plan_query_removes_stopwords()`, `test_planned_query_roundtrip()` | Keep editable query planning deterministic. |
| `project_enterprise_rag/tests/test_filter_suggester.py` | `test_suggest_filters_top_k()`, `test_suggest_filters_excludes_query_terms()` | Ensure filter quality and relevance constraints. |
| `project_enterprise_rag/tests/test_highlighter.py` | `test_highlight_text_marks_expected_terms()` | Guard keyword highlighting behavior for demo reliability. |
| `project_enterprise_rag/scripts/run_local_demo.sh` | `N/A` | One-command local demo startup. |
| `project_enterprise_rag/scripts/reindex_local.py` | `main()` | Force rebuild local index for clean demo resets. |

## Feature Design

### 1) Multi-file input
- Accept multiple files in UI.
- Track `doc_id`, `file_name`, `page`, `chunk_id` metadata.
- Persist index and metadata manifest.
- Re-index incrementally when new files are added.

### 2) Editable generated query
- Add deterministic query planning stage:
  - User query -> planned retrieval query + extracted keywords.
- Show generated query and keyword list in UI before retrieval.
- Allow user to edit planned query and run retrieval with edited value.

### 3) Pretty retrieved chunks + keyword highlighting
- Return structured retrieval records:
  - score, file name, page/chunk metadata, text snippet.
- Render chunk cards in Markdown/HTML with `<mark>` highlights.
- Highlight:
  - query terms
  - selected keyword filters
  - exact keyword matches in chunk text

### 4) Top-k keyword filters
- Build candidate terms from retrieved chunks using TF-IDF (`scikit-learn`).
- Exclude stopwords and already-used query terms.
- Return top-k terms/phrases as clickable filter chips.
- Re-run retrieval with selected filters appended to query and/or metadata filter condition.

## Implementation Phases

### Phase 0: Local-only baseline hardening
- Remove/disable cloud-dependent demo path usage.
- Standardize local runtime entrypoint and module imports.
- Add smoke test for retrieval-only chunk search.

### Phase 1: Multi-file ingestion
- Implement multi-file upload + metadata registry.
- Build/persist index with source metadata.
- Add endpoint/service for ingest status.

### Phase 2: Query planning + edit loop
- Implement deterministic `query_planner.py`.
- Add API contract:
  - `plan_query(user_query)` -> `{planned_query, keywords, rationale}`.
- Add UI controls to edit planned query before retrieval.

### Phase 3: Retrieval rendering + highlighting
- Implement reusable `formatter.py` + `highlighter.py`.
- Display chunk cards with score/source metadata and highlights.
- Keep fallback plain text output for robustness.

### Phase 4: Filter suggestions
- Implement `filter_suggester.py` using top retrieved chunk set.
- Expose top-k filter chips in UI.
- Support iterative retrieval with active filters list.

### Phase 5: Demo hardening
- Add regression tests for:
  - query planning output format
  - highlight rendering
  - filter suggestion stability
  - file registry dedup behavior
- Add local demo startup script and reindex utility.

## Acceptance Criteria
- Multi-file: at least 3 documents can be uploaded and queried in one index.
- Editable query: user can inspect and modify generated retrieval query before search.
- Highlighted output: retrieved chunk view clearly marks query/filter terms.
- Suggested filters: system proposes at least 5 relevant filters for a domain query and applying a filter changes retrieval results.
- Local-only: demo query flow runs without any paid API keys.
- Modularity: each capability has dedicated module(s), no single new file >300 lines.

## Risks and Mitigations
- Risk: weak filter suggestions on sparse corpus.
  - Mitigation: fallback to keyword frequency when TF-IDF confidence is low.
- Risk: local embedding model latency on CPU.
  - Mitigation: cache model load and keep `top_k` bounded for demo.
- Risk: UI complexity for demo.
  - Mitigation: staged layout with collapsible advanced controls.

## Next Execution Order
1. Phase 0 and Phase 1 first (local-only + multi-file foundation).
2. Phase 2 and Phase 3 next (editable query + chunk UX).
3. Phase 4 and Phase 5 last (filter polish + hardening).

---

## Revision Plan (Search-First + Analyst UX)

### Confirmed Interaction Decisions
- Default retrieval mode: `hybrid`.
- Keep `Generate Query Plan` visible.
- Results per page default: `10`.
- Pagination enabled.
- Sorting: relevance, source file, date.
- Facets: curated filters + source file + doc_id.
- Facet click behavior: auto-run search and append selected facet token to planned query.
- Results: snippet-first with expand/collapse full chunk.
- API: preserve compatibility; add fields without breaking existing keys.
- UX style: search + analyst.

### Backend Revision Scope

| File | Planned Function Additions/Changes | Why |
|---|---|---|
| `config/settings.py` | Add defaults: `default_mode`, `default_page_size`, `max_page_size`, `supported_sorts` | Centralized search behavior config.
| `retrieval/query_planner.py` | Add `plan_query_mode(user_query, mode, planner_backend, constraints)`; add support for include/exclude term groups | Conditional and editable smarter query planning.
| `retrieval/retriever.py` | Add `search_chunks(...)` with `mode`, `sort_by`, `page`, `page_size`; return score components | Search-engine-style ranking and pagination.
| `retrieval/retriever.py` | Add hybrid score fusion function (`semantic_score` + `keyword_overlap`) | Implement default hybrid ranking.
| `retrieval/filter_suggester.py` | Add facet counter outputs: `source_file`, `doc_id`, term facets | Analyst-style faceted narrowing.
| `retrieval/formatter.py` | Add snippet builder + expand payload fields | Compact result cards with expand-on-demand.
| `services/rag_service.py` | Expand `search_chunks_service` schema to include `pagination`, `sort`, `mode`, `facets`, `score_breakdown` | One service contract for UI/API.
| `api/routes_query.py` | Extend request model with optional fields: `mode`, `sort_by`, `page`, `page_size`, `planner_backend` | Expose new controls via API while staying backward compatible.

### Frontend Revision Scope

| File | Planned Function Additions/Changes | Why |
|---|---|---|
| `frontend/gradio_app.py` | Add mode selector, sort selector, pagination controls, snippet/expand toggle, facets panel | Search-engine interaction model.
| `frontend/gradio_app.py` | Keep visible plan button and editable planned query field | Preserve current flow while adding search controls.
| `frontend/gradio_app.py` | Facet click handler to append facet to query and auto-run | Matches confirmed user interaction.

### LLM / Non-LLM Planner-Response Strategy

#### Non-LLM path (default)
- Planner backend: deterministic keyword + rules (`retrieval/query_planner.py`).
- Retrieval mode: hybrid ranking without generation.
- Output: chunk snippets + score breakdown only.

#### LLM path (optional toggle)
- Add new module `planning/llm_planner.py`:
  - `generate_query_plan(user_query, context, constraints)`
  - `generate_conditional_query(plan)`
- Add new module `synthesis/answer_builder.py`:
  - `build_cited_answer(query, top_chunks, style)`
  - strict citation to chunk IDs only.
- Add runtime adapters in `llm_chain/` for local model providers:
  - Ollama (`http://localhost:11434`) as first local backend.
  - Optional llama.cpp/OpenAI-compatible local endpoints.
- Keep flags in settings/env:
  - `PLANNER_BACKEND=rules|local_llm`
  - `RESPONSE_BACKEND=none|local_llm`
  - Default: `rules` + `none`.

### Recommended Local Models
- Query planning (cheap/fast): `qwen2.5:7b-instruct` or `llama3.1:8b-instruct`.
- Response synthesis (quality): `qwen2.5:14b-instruct` or `llama3.1:70b` (if hardware supports).
- Keep citation grounding strict: answer must only use retrieved chunk text.

### Validation Additions
- Add tests:
  - `tests/test_retriever_hybrid.py` (score fusion + ranking order)
  - `tests/test_pagination_sort.py` (page boundaries + sort stability)
  - `tests/test_facet_generation.py` (facet counts + selections)
  - `tests/test_llm_toggle_contract.py` (rules vs local_llm backend behavior)

### Phased Execution (Revision)
1. Backend contract + hybrid ranking + pagination/sort.
2. Facets + query append behavior + service/API wiring.
3. UI controls and analyst-oriented results layout.
4. Optional local LLM planner/synthesis toggles (off by default).
5. Regression tests and demo script updates.

### Small-Hardware Ollama Hosting Plan (Demo Mode)

#### Goal
Run LLM-assisted query planning locally on small hardware without blocking retrieval responsiveness.

#### Deployment Recommendation
- Run Ollama on host CPU (not in the same process as Gradio/FastAPI).
- Keep retrieval/indexing path non-LLM by default.
- Use Ollama only for planner enhancement unless response synthesis is explicitly toggled on.

#### Runtime Profile (Low Resource)
- Environment:
  - `OLLAMA_CONTEXT_LENGTH=2048`
  - `OLLAMA_NUM_PARALLEL=1`
  - `OLLAMA_MAX_LOADED_MODELS=1`
  - `OLLAMA_KEEP_ALIVE=30m`
- LLM request defaults:
  - `num_ctx=2048`
  - `num_predict=96..160`
  - `temperature=0.1..0.3`
  - `stream=false`

#### Model Tiers
- Tier A (smallest/fastest): `qwen3:0.6b` for planner-only demos.
- Tier B (balanced): `qwen3:1.7b` for better query rewrites on CPU.
- Keep response generation off by default on small hardware.

#### Integration Contract
- Add config/env wiring:
  - `PLANNER_BACKEND=rules|local_llm`
  - `RESPONSE_BACKEND=none|local_llm`
  - `OLLAMA_BASE_URL=http://127.0.0.1:11434`
  - `OLLAMA_MODEL_PLANNER=qwen3:0.6b`
  - `OLLAMA_MODEL_RESPONSE=qwen3:1.7b`
- API/UI behavior:
  - Default: `PLANNER_BACKEND=rules`, `RESPONSE_BACKEND=none`
  - Optional demo toggle: switch planner to `local_llm` at runtime.

#### Hosting Options
- Host-native Ollama (recommended): lowest overhead and simplest for demo.
- Containerized Ollama (optional):
  - `docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama`

#### Demo Startup Sequence
1. Start Ollama service and warm model (`qwen3:0.6b`).
2. Start enterprise app/API in retrieval-first mode.
3. Enable `local_llm` planner toggle only when demonstrating smarter query generation.
4. Keep answer synthesis toggle off unless latency is acceptable.

#### Guardrails
- Hard timeout for planner requests (e.g., 12s).
- On timeout/error: automatic fallback to rules planner.
- Enforce chunk-grounded responses if response mode is enabled.
