# Local LLM GPU Test Plan (Planner + Response)

## Objective
Validate end-to-end local LLM query planning and response generation on a GPU server using the refreshed hardware corpus.

## Scope
- Planner backend: `local_llm`
- Response backend: `local_llm`
- Dataset: `datasets/semiconductor_ip_demo/docs` (64 hardware-focused docs)
- Test runner: `scripts/run_local_llm_cases.py`
- Cases: `datasets/semiconductor_ip_demo/test_cases/local_llm_cases.json`

## 1) GPU Server Preflight
Run on the GPU server host:

```bash
nvidia-smi
ollama list
curl -fsS http://127.0.0.1:11434/api/tags
```

Expected:
- GPU visible in `nvidia-smi`.
- At least one usable model available (recommended: `qwen3:1.7b`).
- Ollama API reachable.

## 2) Configure Runtime
From `project_enterprise_rag`:

```bash
cp -n .env.example .env
```

Set/confirm these values in `.env`:

```env
API_KEYS=dev-local-key
OPS_API_KEY=dev-local-key
PLANNER_BACKEND=local_llm
RESPONSE_BACKEND=local_llm
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL_PLANNER=qwen3:1.7b
OLLAMA_MODEL_RESPONSE=qwen3:1.7b
INGESTION_DEEP_MEMORY_ENABLED=true
```

## 3) Start API + Worker
```bash
docker compose up -d --build api worker
curl -fsS http://127.0.0.1:8000/v1/health/live
curl -fsS http://127.0.0.1:8000/v1/health/ready
```

Expected:
- `live` endpoint returns `{\"status\":\"live\"}`.
- `ready` endpoint reports healthy dependencies.

## 4) Ingest Refreshed Dataset
```bash
docker compose exec api bash -lc "python -m ops.cli ingest-files \$(find /app/datasets/semiconductor_ip_demo/docs -type f -name '*.md' | tr '\n' ' ') --deep-memory"
```

This runs ingestion from inside the API container so all file paths resolve correctly under `/app`.

Success criteria:
- Job reaches `succeeded`.
- Non-zero `chunks_added`.

## 5) Run Automated Local-LLM Cases
```bash
python scripts/run_local_llm_cases.py \
  --cases datasets/semiconductor_ip_demo/test_cases/local_llm_cases.json \
  --base-url http://127.0.0.1:8000 \
  --api-key dev-local-key
```

Expected:
- `gpu_hbm_bottleneck` passes.
- `motherboard_pcie_cxl_design` passes.
- Final line: `All local-LLM cases passed.`

## 6) Manual API Spot Checks
Planner:
```bash
curl -fsS -X POST http://127.0.0.1:8000/v1/search/plan \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-local-key' \
  -d '{
    "user_query":"Optimize TPU inference throughput with systolic arrays and compiler scheduling",
    "mode":"hybrid",
    "planner_backend":"local_llm",
    "include_terms":["TPU","systolic","compiler"],
    "exclude_terms":["smartphone"]
  }'
```

Search + response:
```bash
curl -fsS -X POST http://127.0.0.1:8000/v1/search \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: dev-local-key' \
  -d '{
    "user_query":"Design motherboard PCIe/CXL topology for multi-GPU AI workstation",
    "mode":"hybrid",
    "planner_backend":"local_llm",
    "response_backend":"local_llm",
    "page":1,
    "page_size":10
  }'
```

Expected:
- `planner_backend`/`backend_used` indicates `local_llm`.
- `chunks` is non-empty.
- `answer` is present and grounded in retrieved content.

## 7) Pass/Fail Gates
Pass if all are true:
- API/worker healthy.
- Ingestion succeeds on refreshed corpus.
- Both automated test cases pass.
- Manual spot checks return local-LLM planned queries and grounded responses.

Fail if any are true:
- Model unavailable / Ollama unreachable.
- Planner/response falls back unexpectedly.
- Case runner reports any failing case.

## 8) Troubleshooting
- `model not found`: `ollama pull qwen3:1.7b` and re-run.
- Connection resets right after restart: wait 10-20s and retry.
- Missing file path errors during ingestion: use container paths (`/app/datasets/...`) for API jobs.
- No answer generated: verify `RESPONSE_BACKEND=local_llm` and Ollama endpoint/model settings.
