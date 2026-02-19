import html
from typing import Dict


def _truncate(text: str, max_chars: int) -> str:
    safe = text or ""
    if len(safe) <= max_chars:
        return safe
    return safe[: max_chars - 3].rstrip() + "..."


def format_chunk_card(chunk: Dict) -> str:
    score = chunk.get("score", "N/A")
    semantic_score = chunk.get("semantic_score", "N/A")
    keyword_overlap = chunk.get("keyword_overlap", "N/A")

    snippet = chunk.get("snippet_highlighted") or html.escape(_truncate(chunk.get("text", ""), 420))
    snippet = snippet.replace("\n", "<br>")

    full_text = chunk.get("text_highlighted") or html.escape(chunk.get("text", ""))
    full_text = full_text.replace("\n", "<br>")

    date = chunk.get("date") or "N/A"
    matched = ", ".join(chunk.get("matched_terms") or []) or "None"

    lines = [
        f"### Result {chunk.get('rank', '?')} | Score: {score}",
        (
            f"`source: {chunk.get('source', 'Unknown')}` "
            f"`doc_id: {chunk.get('doc_id', 'unknown')}` "
            f"`page: {chunk.get('page', 'N/A')}` "
            f"`date: {date}`"
        ),
        (
            f"`semantic: {semantic_score}` "
            f"`keyword_overlap: {keyword_overlap}` "
            f"`matched_terms: {matched}`"
        ),
        snippet,
        "<details><summary>Expand full chunk</summary>",
        full_text,
        "</details>",
    ]
    return "\n".join(lines)


def format_api_chunk(chunk: Dict) -> Dict:
    return {
        "rank": chunk.get("rank"),
        "score": chunk.get("score"),
        "semantic_score": chunk.get("semantic_score"),
        "keyword_overlap": chunk.get("keyword_overlap"),
        "source": chunk.get("source"),
        "page": chunk.get("page"),
        "date": chunk.get("date"),
        "doc_id": chunk.get("doc_id"),
        "chunk_id": chunk.get("chunk_id"),
        "matched_terms": chunk.get("matched_terms", []),
        "text": chunk.get("text"),
        "snippet": _truncate(chunk.get("text", ""), 420),
        "text_highlighted": chunk.get("text_highlighted"),
        "snippet_highlighted": chunk.get("snippet_highlighted"),
        "metadata": chunk.get("metadata", {}),
    }
