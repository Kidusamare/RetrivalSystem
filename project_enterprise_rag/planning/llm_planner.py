import json
import re
from typing import Dict, List, Optional
from urllib import error, request


def _extract_first_json_object(text: str) -> Dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty LLM planner response")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM planner response")
    return json.loads(match.group(0))


def _normalize_list(values: Optional[List[str]]) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values or []:
        cleaned = (value or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output


def generate_query_plan(
    *,
    user_query: str,
    mode: str,
    constraints: Optional[Dict],
    base_url: str,
    model: str,
    timeout_seconds: int,
) -> Dict:
    include_terms = _normalize_list((constraints or {}).get("include_terms"))
    exclude_terms = _normalize_list((constraints or {}).get("exclude_terms"))

    instruction = {
        "task": "Rewrite user query for retrieval.",
        "requirements": [
            "Return only JSON",
            "Keep domain-specific meaning",
            "Prefer concise search phrases",
            "Respect include_terms and exclude_terms",
        ],
        "schema": {
            "planned_query": "string",
            "rationale": "string",
            "include_terms": ["string"],
            "exclude_terms": ["string"],
        },
    }

    prompt = (
        f"Instruction: {json.dumps(instruction)}\n"
        f"Mode: {mode}\n"
        f"User Query: {user_query}\n"
        f"Include Terms: {include_terms}\n"
        f"Exclude Terms: {exclude_terms}\n"
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 2048,
            "num_predict": 160,
        },
    }

    url = base_url.rstrip("/") + "/api/generate"
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(f"Ollama planner request failed: {exc}") from exc

    outer = json.loads(body)
    raw_response = outer.get("response", "")
    parsed = _extract_first_json_object(raw_response)

    planned_query = (parsed.get("planned_query") or "").strip()
    rationale = (parsed.get("rationale") or "").strip()

    if not planned_query:
        raise ValueError("LLM planner did not return planned_query")

    return {
        "planned_query": planned_query,
        "rationale": rationale or "LLM-generated retrieval query rewrite.",
        "include_terms": _normalize_list(parsed.get("include_terms") or include_terms),
        "exclude_terms": _normalize_list(parsed.get("exclude_terms") or exclude_terms),
        "backend_used": "local_llm",
    }
