from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Dict, List

import yaml
from llama_index.core import Document

from db.session import run_migrations
from ingestion.chunker import chunk_documents
from ingestion.index_builder import load_or_create_index, persist_index, upsert_chunks
from retrieval.runtime_engine import search_chunks
from services.job_service import record_eval_run
from evaluation.metrics import precision_at_k


def _load_gold_dataset(dataset_path: Path) -> Dict:
    with dataset_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload


def _build_fixture_index(fixtures: List[Dict], persist_dir: Path) -> None:
    docs = []
    for fixture in fixtures:
        doc_id = str(fixture["doc_id"])
        file_name = str(fixture.get("file_name") or f"{doc_id}.md")
        text = str(fixture.get("text") or "")
        docs.append(
            Document(
                text=text,
                metadata={
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "source_path": f"fixture://{file_name}",
                    "source": "evaluation_fixture",
                },
            )
        )

    nodes = chunk_documents(documents=docs, chunk_size=500, chunk_overlap=40)
    for index, node in enumerate(nodes, start=1):
        metadata = dict(node.metadata or {})
        doc_id = str(metadata.get("doc_id") or "fixture")
        metadata["chunk_id"] = f"{doc_id}_chunk_{index}"
        node.metadata = metadata

    index = load_or_create_index(persist_dir)
    index = upsert_chunks(index, nodes)
    persist_index(index, persist_dir)


def run_precision_eval(dataset_path: str) -> Dict:
    dataset = _load_gold_dataset(Path(dataset_path))
    fixtures = dataset.get("fixtures") or []
    queries = dataset.get("queries") or []
    k = int(dataset.get("k") or 10)

    if not fixtures or not queries:
        raise ValueError("Dataset must contain fixtures and queries entries.")

    with tempfile.TemporaryDirectory(prefix="eval_index_") as tmp_dir:
        persist_dir = Path(tmp_dir)
        _build_fixture_index(fixtures, persist_dir)

        per_query = []
        for row in queries:
            query = str(row.get("query") or "").strip()
            relevant = [str(value) for value in (row.get("relevant_doc_ids") or [])]
            if not query:
                continue
            result = search_chunks(
                persist_dir=persist_dir,
                planned_query=query,
                query_terms=None,
                active_filters=[],
                mode="hybrid",
                sort_by="relevance",
                page=1,
                page_size=k,
            )
            predicted = []
            seen = set()
            for chunk in result.get("chunks") or []:
                doc_id = str(chunk.get("doc_id") or "")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                predicted.append(doc_id)

            score = precision_at_k(predicted, relevant, k=k)
            per_query.append({"query": query, "precision": score, "predicted": predicted, "relevant": relevant})

    if not per_query:
        raise ValueError("No query rows were evaluated.")

    avg_precision = sum(item["precision"] for item in per_query) / len(per_query)

    run_migrations()
    run_id = record_eval_run(
        dataset_name=str(dataset.get("dataset") or Path(dataset_path).stem),
        metric_name=f"precision@{k}",
        metric_value=avg_precision,
        details={"queries": per_query},
    )

    return {
        "run_id": run_id,
        "dataset": dataset.get("dataset") or Path(dataset_path).stem,
        "metric": f"precision@{k}",
        "value": avg_precision,
        "queries": per_query,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval precision evaluation.")
    parser.add_argument("--dataset", required=True, help="Path to YAML evaluation set.")
    parser.add_argument("--min-precision", type=float, default=0.9)
    args = parser.parse_args()

    result = run_precision_eval(args.dataset)
    print(f"Evaluation run: {result['run_id']}")
    print(f"Dataset: {result['dataset']}")
    print(f"Metric: {result['metric']} = {result['value']:.4f}")

    if result["value"] < float(args.min_precision):
        raise SystemExit(f"Precision threshold failed: {result['value']:.4f} < {args.min_precision:.4f}")


if __name__ == "__main__":
    main()
