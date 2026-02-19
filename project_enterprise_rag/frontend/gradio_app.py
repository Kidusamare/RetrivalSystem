from __future__ import annotations

import json
from typing import Iterable, List, Tuple

import gradio as gr
import requests

from config.settings import get_settings


def _extract_file_paths(files: Iterable) -> List[str]:
    paths: List[str] = []
    for item in files or []:
        if isinstance(item, str):
            paths.append(item)
            continue
        if hasattr(item, "name"):
            paths.append(str(item.name))
            continue
        if isinstance(item, dict) and item.get("name"):
            paths.append(str(item["name"]))
    return paths


def _parse_csv_terms(raw_text: str) -> List[str]:
    terms = []
    seen = set()
    for token in (raw_text or "").split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        terms.append(cleaned)
    return terms


def _append_tokens_to_query(planned_query: str, tokens: List[str]) -> str:
    query = (planned_query or "").strip()
    lower_query = query.lower()
    for token in tokens:
        cleaned = (token or "").strip()
        if not cleaned:
            continue
        if cleaned.lower() in lower_query:
            continue
        query = f"{query} {cleaned}".strip()
        lower_query = query.lower()
    return query


def _facet_markdown(facets: dict) -> str:
    terms = facets.get("term", [])
    if not terms:
        return "### Top Keyword Terms\n- none"
    preview = ", ".join([f"{row['label']} ({row['count']})" for row in terms[:12]])
    return f"### Top Keyword Terms\n- {preview}"


def _jobs_markdown(rows: List[dict]) -> str:
    if not rows:
        return "### Recent Jobs\n- none"

    lines = ["### Recent Jobs"]
    for row in rows:
        lines.append(
            "- `{id}` | `{type}` | `{status}` | progress={progress}".format(
                id=row.get("id"),
                type=row.get("type"),
                status=row.get("status"),
                progress=row.get("progress"),
            )
        )
    return "\n".join(lines)


def _api_base_url() -> str:
    return get_settings().ops_api_base_url.rstrip("/")


def _api_headers() -> dict:
    settings = get_settings()
    return {
        "Content-Type": "application/json",
        "X-API-Key": settings.ops_api_key,
    }


def _post(path: str, payload: dict) -> dict:
    response = requests.post(f"{_api_base_url()}{path}", headers=_api_headers(), json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def _get(path: str) -> dict:
    response = requests.get(f"{_api_base_url()}{path}", headers=_api_headers(), timeout=45)
    response.raise_for_status()
    return response.json()


def on_ingest_files(files, deep_memory_enabled: bool) -> Tuple[str, str]:
    try:
        file_paths = _extract_file_paths(files)
        payload = {
            "file_paths": file_paths,
            "options": {
                "chunk_size": get_settings().chunk_size,
                "chunk_overlap": get_settings().chunk_overlap,
                "deep_memory": bool(deep_memory_enabled),
                "dedupe": "sha256",
            },
        }
        result = _post("/v1/ingestions/files", payload)
        md = (
            "### Ingestion Job Queued\n"
            f"- `job_id: {result['job_id']}`\n"
            f"- `status: {result['status']}`\n"
            f"- `deep_memory: {bool(deep_memory_enabled)}`\n"
            "- use **Refresh Job Status** to monitor progress"
        )
        return md, result["job_id"]
    except Exception as exc:  # noqa: BLE001
        return f"### Ingestion Error\n`{exc}`", ""


def on_sync_patentsview(keywords_csv: str, max_records: int, deep_memory_enabled: bool) -> Tuple[str, str]:
    try:
        keywords = _parse_csv_terms(keywords_csv)
        payload = {
            "query": {"keywords": keywords, "max_records": int(max_records)},
            "options": {
                "chunk_size": get_settings().chunk_size,
                "chunk_overlap": get_settings().chunk_overlap,
                "deep_memory": bool(deep_memory_enabled),
                "dedupe": "patent_id",
            },
        }
        result = _post("/v1/ingestions/patentsview", payload)
        md = (
            "### PatentsView Sync Queued\n"
            f"- `job_id: {result['job_id']}`\n"
            f"- `status: {result['status']}`\n"
            f"- `deep_memory: {bool(deep_memory_enabled)}`\n"
            "- use **Refresh Job Status** to monitor progress"
        )
        return md, result["job_id"]
    except Exception as exc:  # noqa: BLE001
        return f"### PatentsView Sync Error\n`{exc}`", ""


def on_refresh_job(job_id: str) -> str:
    if not (job_id or "").strip():
        return "### Job Status\n- no job id"

    try:
        row = _get(f"/v1/jobs/{job_id.strip()}")
        summary = row.get("result_summary") or {}
        return (
            "### Job Status\n"
            f"- `id: {row.get('id')}`\n"
            f"- `type: {row.get('type')}`\n"
            f"- `status: {row.get('status')}`\n"
            f"- `progress: {row.get('progress')}`\n"
            f"- `started_at: {row.get('started_at')}`\n"
            f"- `finished_at: {row.get('finished_at')}`\n"
            f"- `error: {row.get('error')}`\n"
            f"- `summary: {json.dumps(summary, ensure_ascii=False)}`"
        )
    except Exception as exc:  # noqa: BLE001
        return f"### Job Status Error\n`{exc}`"


def on_list_jobs(status_filter: str, limit: int) -> str:
    try:
        safe_limit = max(1, min(int(limit), 200))
        path = f"/v1/jobs?limit={safe_limit}"
        selected_status = (status_filter or "").strip().lower()
        if selected_status and selected_status != "all":
            path = f"{path}&status={selected_status}"
        payload = _get(path)
        return _jobs_markdown(payload.get("jobs") or [])
    except Exception as exc:  # noqa: BLE001
        return f"### Recent Jobs Error\n`{exc}`"


def on_plan_query(
    user_query: str,
    mode: str,
    planner_backend: str,
    include_terms_csv: str,
    exclude_terms_csv: str,
    active_filters: List[str],
) -> Tuple[str, str, str, str]:
    include_terms = _parse_csv_terms(include_terms_csv)
    exclude_terms = _parse_csv_terms(exclude_terms_csv)

    plan = _post(
        "/v1/search/plan",
        {
            "user_query": user_query,
            "mode": mode,
            "planner_backend": planner_backend,
            "include_terms": include_terms,
            "exclude_terms": exclude_terms,
            "active_filters": active_filters,
        },
    )
    backend_used = plan.get("backend_used", "rules")
    rationale = f"{plan.get('rationale', '')} [backend={backend_used}]"

    return plan["planned_query"], ", ".join(plan.get("keywords") or []), rationale, backend_used


def on_search(
    user_query: str,
    planned_query: str,
    active_filters: List[str],
    mode: str,
    sort_by: str,
    page: int,
    page_size: int,
    planner_backend: str,
    response_backend: str,
    include_terms_csv: str,
    exclude_terms_csv: str,
):
    include_terms = _parse_csv_terms(include_terms_csv)
    exclude_terms = _parse_csv_terms(exclude_terms_csv)

    try:
        result = _post(
            "/v1/search",
            {
                "user_query": user_query,
                "planned_query": planned_query,
                "active_filters": active_filters,
                "mode": mode,
                "sort_by": sort_by,
                "page": int(page),
                "page_size": int(page_size),
                "planner_backend": planner_backend,
                "response_backend": response_backend,
                "include_terms": include_terms,
                "exclude_terms": exclude_terms,
            },
        )

        if result.get("chunk_cards"):
            cards = "## Retrieved Chunks\n\n" + "\n\n---\n\n".join(result["chunk_cards"])
        else:
            cards = "## Retrieved Chunks\n\nNo chunks found for this query."

        if result.get("answer"):
            cards = cards + "\n\n## Optional LLM Answer\n\n" + result["answer"]

        facets = result.get("facets", {"term": []})
        filters_update = gr.update(choices=result.get("facet_choices", []), value=result.get("active_filters", []))
        debug_json = json.dumps(
            {
                "planned_query": result.get("planned_query"),
                "normalized_query": result.get("normalized_query"),
                "keywords": result.get("keywords"),
                "mode": result.get("mode"),
                "sort_by": result.get("sort_by"),
                "pagination": result.get("pagination"),
                "active_filters": result.get("active_filters"),
                "planner_backend": result.get("planner_backend"),
                "response_backend": result.get("response_backend"),
                "search_meta": result.get("search_meta"),
            },
            indent=2,
        )
        facet_md = _facet_markdown(facets)

        return (
            cards,
            filters_update,
            debug_json,
            facet_md,
            result.get("normalized_query", planned_query),
            result.get("active_filters", []),
        )
    except Exception as exc:  # noqa: BLE001
        return (
            f"## Retrieved Chunks\n\nSearch failed: `{exc}`",
            gr.update(choices=[], value=[]),
            json.dumps({"error": str(exc)}, indent=2),
            "### Top Keyword Terms\n- unavailable",
            planned_query,
            active_filters or [],
        )


def on_apply_filter(
    user_query: str,
    planned_query: str,
    active_filters: List[str],
    previous_filters: List[str],
    mode: str,
    sort_by: str,
    page: int,
    page_size: int,
    planner_backend: str,
    response_backend: str,
    include_terms_csv: str,
    exclude_terms_csv: str,
):
    previous = set(previous_filters or [])
    added = [token for token in (active_filters or []) if token not in previous]
    updated_query = _append_tokens_to_query(planned_query=planned_query, tokens=added)

    return on_search(
        user_query=user_query,
        planned_query=updated_query,
        active_filters=active_filters,
        mode=mode,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        planner_backend=planner_backend,
        response_backend=response_backend,
        include_terms_csv=include_terms_csv,
        exclude_terms_csv=exclude_terms_csv,
    )


def build_ui() -> gr.Blocks:
    with gr.Blocks() as demo:
        gr.Markdown("# Strategic IP Retrieval Ops Console")
        gr.Markdown("Internal operations UI powered by `/v1` API routes.")

        active_filter_state = gr.State([])
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Async Ingestion")
                file_input = gr.File(label="Upload Documents", file_count="multiple", type="filepath")
                ingest_btn = gr.Button("Queue File Ingestion")
                ingest_status = gr.Markdown("No ingestion job queued yet.")

                patents_keywords = gr.Textbox(
                    label="PatentsView Keywords (comma-separated)",
                    value="semiconductor, dielectric, interconnect",
                )
                patents_max_records = gr.Number(label="PatentsView max records", value=50, precision=0)
                deep_memory_toggle = gr.Checkbox(
                    label="Enable LlamaIndex Deep Memory Chunking",
                    value=bool(get_settings().ingestion_deep_memory_enabled),
                )
                patents_btn = gr.Button("Queue PatentsView Sync")
                patents_status = gr.Markdown("No PatentsView sync job queued yet.")

                job_id_box = gr.Textbox(label="Current Job ID", value="", interactive=True)
                refresh_job_btn = gr.Button("Refresh Job Status")
                job_status_md = gr.Markdown("### Job Status\n- no job selected")
                with gr.Row():
                    job_status_filter = gr.Dropdown(
                        label="Recent Jobs Filter",
                        choices=["all", "queued", "running", "succeeded", "failed", "cancelled"],
                        value="all",
                    )
                    job_limit = gr.Number(label="Recent Jobs Limit", value=20, precision=0)
                refresh_jobs_btn = gr.Button("Refresh Jobs List")
                jobs_list_md = gr.Markdown("### Recent Jobs\n- none")

            with gr.Column(scale=2):
                gr.Markdown("## Query + Search")
                user_query = gr.Textbox(label="User Query", placeholder="Enter your query...")
                planned_query = gr.Textbox(
                    label="Planned Query (Editable)",
                    placeholder="Generate query plan first, then edit if needed.",
                )

                with gr.Row():
                    mode = gr.Dropdown(label="Retrieval Mode", choices=["hybrid", "semantic", "keyword"], value="hybrid")
                    sort_by = gr.Dropdown(label="Sort By", choices=["relevance", "source", "date"], value="relevance")
                    page_size = gr.Dropdown(label="Results Per Page", choices=[10, 20, 50], value=10)
                    page = gr.Number(label="Page", value=1, precision=0)

                with gr.Row():
                    planner_backend = gr.Dropdown(label="Planner Backend", choices=["rules", "local_llm"], value="rules")
                    response_backend = gr.Dropdown(label="Response Backend", choices=["none", "local_llm"], value="none")

                with gr.Row():
                    include_terms = gr.Textbox(label="Include Terms (comma-separated)", placeholder="semiconductor, dielectric")
                    exclude_terms = gr.Textbox(label="Exclude Terms (comma-separated)", placeholder="memory, optical")

                with gr.Row():
                    plan_btn = gr.Button("Generate Query Plan")
                    search_btn = gr.Button("Search Chunks")

                keywords_box = gr.Textbox(label="Extracted Keywords", interactive=False)
                rationale_box = gr.Textbox(label="Planning Rationale", interactive=False)
                backend_box = gr.Textbox(label="Planner Backend Used", interactive=False)
                filters_box = gr.CheckboxGroup(label="Top Keyword Filters (click to apply)")

        facets_md = gr.Markdown("### Top Keyword Terms\n- none")
        results_md = gr.Markdown("Run a search to see chunk results.")
        debug_box = gr.Code(label="Search Metadata", language="json")

        ingest_btn.click(on_ingest_files, inputs=[file_input, deep_memory_toggle], outputs=[ingest_status, job_id_box])
        patents_btn.click(
            on_sync_patentsview,
            inputs=[patents_keywords, patents_max_records, deep_memory_toggle],
            outputs=[patents_status, job_id_box],
        )
        refresh_job_btn.click(on_refresh_job, inputs=job_id_box, outputs=job_status_md)
        refresh_jobs_btn.click(on_list_jobs, inputs=[job_status_filter, job_limit], outputs=jobs_list_md)

        plan_btn.click(
            on_plan_query,
            inputs=[user_query, mode, planner_backend, include_terms, exclude_terms, filters_box],
            outputs=[planned_query, keywords_box, rationale_box, backend_box],
        )

        search_inputs = [
            user_query,
            planned_query,
            filters_box,
            mode,
            sort_by,
            page,
            page_size,
            planner_backend,
            response_backend,
            include_terms,
            exclude_terms,
        ]
        search_outputs = [results_md, filters_box, debug_box, facets_md, planned_query, active_filter_state]

        search_btn.click(on_search, inputs=search_inputs, outputs=search_outputs)

        filters_box.change(
            on_apply_filter,
            inputs=[
                user_query,
                planned_query,
                filters_box,
                active_filter_state,
                mode,
                sort_by,
                page,
                page_size,
                planner_backend,
                response_backend,
                include_terms,
                exclude_terms,
            ],
            outputs=search_outputs,
        )

    return demo
