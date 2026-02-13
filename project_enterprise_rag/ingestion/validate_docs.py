import json
import os


def validate_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) and not isinstance(data, dict):
        raise ValueError("Invalid JSON structure")

    print(f"[OK] Validated: {path}")


if __name__ == "__main__":
    validate_file("project-enterprise-rag/ingestion/output_normalized.json")
    validate_file("project-enterprise-rag/ingestion/raw_docs.json")
