#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config.settings import get_settings, resolve_paths
from services.rag_service import ingest_files_service


def _clear_index_files(storage_dir: Path) -> None:
    for name in (
        "docstore.json",
        "index_store.json",
        "default__vector_store.json",
        "graph_store.json",
        "image__vector_store.json",
    ):
        target = storage_dir / name
        if target.exists():
            target.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex local documents for enterprise RAG demo.")
    parser.add_argument("files", nargs="*", help="Files to ingest and index.")
    parser.add_argument("--clear", action="store_true", help="Clear existing index before ingest.")
    parser.add_argument(
        "--clear-registry",
        action="store_true",
        help="Clear file registry and treat all files as new.",
    )
    args = parser.parse_args()

    settings = resolve_paths(get_settings())
    if args.clear:
        _clear_index_files(settings.storage_dir)
    if args.clear_registry and settings.registry_path.exists():
        settings.registry_path.unlink()
        resolve_paths(settings)

    if not args.files:
        print("No files provided. Nothing indexed.")
        return

    result = ingest_files_service(args.files)
    print(result["message"])
    print(f"New files: {result['ingested_files_count']}")
    print(f"Chunks added: {result['chunks_added']}")


if __name__ == "__main__":
    main()
