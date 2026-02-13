from typing import Dict


def format_chunk_card(chunk: Dict) -> str:
    score = chunk.get("score", "N/A")
    text = chunk.get("text_highlighted") or chunk.get("text", "")
    text = text.replace("\n", "<br>")

    lines = [
        f"### Chunk {chunk.get('rank', '?')} | Score: {score}",
        f"`source: {chunk.get('source', 'Unknown')}` `page: {chunk.get('page', 'N/A')}`",
        text,
    ]
    return "\n".join(lines)


def format_api_chunk(chunk: Dict) -> Dict:
    return {
        "rank": chunk.get("rank"),
        "score": chunk.get("score"),
        "source": chunk.get("source"),
        "page": chunk.get("page"),
        "doc_id": chunk.get("doc_id"),
        "chunk_id": chunk.get("chunk_id"),
        "text": chunk.get("text"),
        "text_highlighted": chunk.get("text_highlighted"),
        "metadata": chunk.get("metadata", {}),
    }

