import json
from typing import Iterable, List, Tuple

import gradio as gr

from services.rag_service import ingest_files_service, plan_query_service, search_chunks_service


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


def on_ingest_files(files) -> str:
    try:
        file_paths = _extract_file_paths(files)
        result = ingest_files_service(file_paths)
        return (
            f"### Ingestion Status\n"
            f"- `{result['message']}`\n"
            f"- `new files: {result['ingested_files_count']}`\n"
            f"- `chunks added: {result['chunks_added']}`\n"
            f"- `total registered: {result['total_registered_files']}`"
        )
    except Exception as exc:
        return f"### Ingestion Error\n`{exc}`"


def on_plan_query(user_query: str) -> Tuple[str, str, str]:
    plan = plan_query_service(user_query)
    return plan["planned_query"], ", ".join(plan["keywords"]), plan["rationale"]


def on_search(
    user_query: str,
    planned_query: str,
    active_filters: List[str],
    top_k: int,
):
    try:
        result = search_chunks_service(
            user_query=user_query,
            planned_query=planned_query,
            active_filters=active_filters,
            top_k=top_k,
        )

        if result["chunk_cards"]:
            cards = "## Retrieved Chunks\n\n" + "\n\n---\n\n".join(result["chunk_cards"])
        else:
            cards = "## Retrieved Chunks\n\nNo chunks found for this query."

        filters_update = gr.update(choices=result["suggested_filters"], value=active_filters or [])
        debug_json = json.dumps(
            {
                "planned_query": result["planned_query"],
                "keywords": result["keywords"],
                "active_filters": result["active_filters"],
                "suggested_filters": result["suggested_filters"],
                "total_chunks": result["total_chunks"],
            },
            indent=2,
        )
        return cards, filters_update, debug_json
    except Exception as exc:
        return (
            f"## Retrieved Chunks\n\nSearch failed: `{exc}`",
            gr.update(choices=[], value=[]),
            json.dumps({"error": str(exc)}, indent=2),
        )


def on_apply_filter(
    user_query: str,
    planned_query: str,
    active_filters: List[str],
    top_k: int,
):
    return on_search(user_query, planned_query, active_filters, top_k)


def build_ui() -> gr.Blocks:
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Enterprise RAG Retrieval Demo (Local + No Cost)")
        gr.Markdown("Upload files, inspect generated query, edit it, and view highlighted chunks.")

        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(
                    label="Upload Documents",
                    file_count="multiple",
                    type="filepath",
                )
                ingest_btn = gr.Button("Ingest Files")
                ingest_status = gr.Markdown("No files ingested yet.")

            with gr.Column(scale=2):
                user_query = gr.Textbox(label="User Query", placeholder="Enter your query...")
                planned_query = gr.Textbox(
                    label="Planned Query (Editable)",
                    placeholder="Generate query plan first, then edit if needed.",
                )
                with gr.Row():
                    plan_btn = gr.Button("Generate Query Plan")
                    search_btn = gr.Button("Search Chunks")

                keywords_box = gr.Textbox(label="Extracted Keywords", interactive=False)
                rationale_box = gr.Textbox(label="Planning Rationale", interactive=False)
                filters_box = gr.CheckboxGroup(label="Suggested Filters")
                top_k = gr.Slider(label="Top K Chunks", minimum=1, maximum=15, step=1, value=5)

        results_md = gr.Markdown("Run a search to see chunk results.")
        debug_box = gr.Code(label="Search Metadata", language="json")

        ingest_btn.click(on_ingest_files, inputs=file_input, outputs=ingest_status)
        plan_btn.click(
            on_plan_query,
            inputs=user_query,
            outputs=[planned_query, keywords_box, rationale_box],
        )
        search_btn.click(
            on_search,
            inputs=[user_query, planned_query, filters_box, top_k],
            outputs=[results_md, filters_box, debug_box],
        )
        filters_box.change(
            on_apply_filter,
            inputs=[user_query, planned_query, filters_box, top_k],
            outputs=[results_md, filters_box, debug_box],
        )

    return demo
