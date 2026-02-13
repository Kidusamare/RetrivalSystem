import json
import os
from typing import List, Dict


def load_normalized_pages(path: str) -> List[Dict]:
    """Load normalized LlamaParse output."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Normalized JSON file missing at {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def chunk_text(text: str, max_tokens: int = 800) -> List[str]:
    """Simple chunker — splits text by paragraphs."""
    paras = text.split("\n")
    chunks = []
    current = ""

    for p in paras:
        if len(current) + len(p) < max_tokens:
            current += p + "\n"
        else:
            chunks.append(current.strip())
            current = p + "\n"

    if current:
        chunks.append(current.strip())
    return chunks


def build_raw_docs(pages: List[Dict]) -> List[Dict]:
    """Creates chunked raw docs that are ready for embeddings."""
    raw_docs = []

    for page in pages:
        page_num = page["page"]
        txt = page["text"]

        chunks = chunk_text(txt)

        for idx, c in enumerate(chunks):
            raw_docs.append({
                "id": f"page{page_num}_chunk{idx}",
                "page": page_num,
                "content": c
            })

    return raw_docs


def save_raw_docs(raw_docs: List[Dict], output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_docs, f, indent=4, ensure_ascii=False)

    print(f"[OK] Raw docs saved → {output_path}")


if __name__ == "__main__":
    normalized_path = "project-enterprise-rag/ingestion/output_normalized.json"
    pages = load_normalized_pages(normalized_path)
    raw_docs = build_raw_docs(pages)
    save_raw_docs(raw_docs, "project-enterprise-rag/ingestion/raw_docs.json")
