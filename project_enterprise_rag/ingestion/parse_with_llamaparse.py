import json
import os
from typing import List, Dict


def load_parsed_json(json_path: str) -> Dict:
    """Load LlamaParse JSON file."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Parsed JSON file not found at {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_page_text(parsed_json: Dict) -> List[Dict]:
    """Extract text from each page with structure preserved."""
    pages = parsed_json.get("pages", [])
    results = []

    for page in pages:
        page_num = page.get("page", None)
        raw_text = page.get("text", "")
        markdown = page.get("md", "")
        images = page.get("images", [])

        results.append({
            "page": page_num,
            "text": raw_text,
            "markdown": markdown,
            "images": images
        })

    return results


def save_normalized_output(output: List[Dict], output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"[OK] Normalized parsed JSON saved → {output_path}")


if __name__ == "__main__":
    """Executed only if run manually"""
    from dotenv import load_dotenv
    load_dotenv()

    json_path = os.getenv("PARSED_JSON_PATH")

    data = load_parsed_json(json_path)
    pages = extract_page_text(data)

    save_normalized_output(
        pages,
        "project-enterprise-rag/ingestion/output_normalized.json"
    )
