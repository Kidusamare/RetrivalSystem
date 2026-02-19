import json
from typing import Dict, Iterable, Optional
from urllib import error, request


def _build_chunk_context(chunks: Iterable[Dict], max_chunks: int = 6) -> str:
    lines = []
    for chunk in list(chunks)[:max_chunks]:
        chunk_id = chunk.get("chunk_id") or "unknown"
        source = chunk.get("source") or "Unknown"
        text = (chunk.get("text") or "").strip().replace("\n", " ")
        if len(text) > 900:
            text = text[:897] + "..."
        lines.append(f"[{chunk_id}] source={source} text={text}")
    return "\n".join(lines)


def build_cited_answer(
    *,
    query: str,
    chunks: Iterable[Dict],
    backend: str,
    base_url: str,
    model: str,
    timeout_seconds: int,
) -> Optional[str]:
    if backend != "local_llm":
        return None

    context = _build_chunk_context(chunks)
    if not context:
        return None

    prompt = (
        "You are a strict retrieval-grounded analyst. "
        "Answer ONLY from provided chunks and cite chunk ids in brackets like [chunk_id].\n"
        f"User Query: {query}\n"
        f"Chunks:\n{context}\n"
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 2048,
            "num_predict": 220,
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
    except error.URLError:
        return None

    outer = json.loads(body)
    answer = (outer.get("response") or "").strip()
    return answer or None
