import json
import os
from llama_index.core import Document, VectorStoreIndex
from project_enterprise_rag.store.mixedbread_client import get_embedding_model

INPUT_JSON = "project_enterprise_rag/ingestion/output_normalized.json"
PERSIST_DIR = "project_enterprise_rag/storage"

def main():
    print("Loading normalized chunks...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    documents = []

    for idx, chunk in enumerate(chunks):
        text = chunk.get("text", "").strip()
        if not text:
            continue

        documents.append(
            Document(
                text=text,
                metadata={
                    "page": chunk.get("page"),
                    "source": "uploaded_document"
                }
            )
        )

    print(f"Loaded {len(documents)} document chunks")

    embed_model = get_embedding_model()

    print("Building vector index...")
    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=embed_model
    )

    index.storage_context.persist(persist_dir=PERSIST_DIR)

    print(f"Vector index persisted to: {PERSIST_DIR}")

if __name__ == "__main__":
    main()
