from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence


def normalize_filter_tokens(active_filters: Optional[Iterable[str]]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for raw in active_filters or []:
        token = (raw or "").strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(token)
    return cleaned


def parse_active_filters(active_filters: Optional[Iterable[str]]) -> Dict[str, List[str]]:
    keyword_terms: List[str] = []
    source_filters: List[str] = []
    doc_filters: List[str] = []

    for token in normalize_filter_tokens(active_filters):
        lowered = token.lower()
        if lowered.startswith("source:"):
            source_filters.append(token.split(":", 1)[1].strip())
            continue
        if lowered.startswith("doc:"):
            doc_filters.append(token.split(":", 1)[1].strip())
            continue
        keyword_terms.append(token)

    return {
        "keywords": keyword_terms,
        "source": source_filters,
        "doc": doc_filters,
        "tokens": normalize_filter_tokens(active_filters),
    }


def apply_active_filters(planned_query: str, active_filters: Optional[Iterable[str]]) -> str:
    base = (planned_query or "").strip()
    lower_base = base.lower()
    for token in normalize_filter_tokens(active_filters):
        if token.lower() in lower_base:
            continue
        base = f"{base} {token}".strip()
        lower_base = base.lower()
    return base


def extract_date_value(metadata: Dict) -> tuple[str, float]:
    candidates = [
        metadata.get("patent_date"),
        metadata.get("date"),
        metadata.get("source_modified_at"),
        metadata.get("created_at"),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        raw = str(candidate).strip()
        if not raw:
            continue

        if raw.isdigit():
            timestamp = float(raw)
            return raw, timestamp

        iso_like = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_like)
            return raw, dt.timestamp()
        except ValueError:
            pass

        if len(raw) == 10:
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d")
                return raw, dt.timestamp()
            except ValueError:
                pass

    return "", 0.0


def compute_keyword_overlap(text: str, query_terms: Sequence[str]) -> tuple[float, List[str]]:
    normalized_terms = []
    seen = set()
    for term in query_terms:
        cleaned = (term or "").strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_terms.append(cleaned)

    if not normalized_terms:
        return 0.0, []

    haystack = (text or "").lower()
    matched = [term for term in normalized_terms if term in haystack]
    return len(matched) / len(normalized_terms), matched


def normalize_semantic_scores(records: List[Dict]) -> None:
    if not records:
        return

    values = [float(record.get("semantic_score_raw") or 0.0) for record in records]
    minimum = min(values)
    maximum = max(values)

    if maximum == minimum:
        normalized = 1.0 if maximum > 0 else 0.0
        for record in records:
            record["semantic_score"] = normalized
        return

    denom = maximum - minimum
    for record in records:
        raw = float(record.get("semantic_score_raw") or 0.0)
        record["semantic_score"] = (raw - minimum) / denom


def fuse_scores(*, semantic_score: float, keyword_overlap: float, mode: str) -> float:
    if mode == "semantic":
        return semantic_score
    if mode == "keyword":
        return 0.9 * keyword_overlap + 0.1 * semantic_score
    return 0.65 * semantic_score + 0.35 * keyword_overlap


def sort_chunk_records(records: List[Dict], sort_by: str) -> List[Dict]:
    mode = (sort_by or "relevance").strip().lower()

    if mode == "source":
        return sorted(
            records,
            key=lambda item: (
                (item.get("source") or "").lower(),
                -float(item.get("score") or 0.0),
            ),
        )

    if mode == "date":
        return sorted(
            records,
            key=lambda item: (
                -float(item.get("date_ts") or 0.0),
                -float(item.get("score") or 0.0),
            ),
        )

    return sorted(records, key=lambda item: float(item.get("score") or 0.0), reverse=True)


def paginate_records(records: List[Dict], page: int, page_size: int) -> Dict:
    total = len(records)
    page_size = max(1, int(page_size))
    total_pages = max(1, (total + page_size - 1) // page_size)
    safe_page = max(1, min(int(page), total_pages))

    start = (safe_page - 1) * page_size
    end = start + page_size
    items = records[start:end]

    return {
        "items": items,
        "page": safe_page,
        "page_size": page_size,
        "total_results": total,
        "total_pages": total_pages,
    }


def node_key(metadata: Dict, text: str) -> str:
    chunk_id = metadata.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    return f"{metadata.get('doc_id', 'unknown')}::{hash(text)}"


def resolve_source(metadata: Dict) -> str:
    return metadata.get("file_name") or metadata.get("filename") or metadata.get("source") or "Unknown"


def record_passes_structured_filters(record: Dict, parsed_filters: Dict[str, List[str]]) -> bool:
    if parsed_filters["source"]:
        allowed = {item.lower() for item in parsed_filters["source"]}
        if (record.get("source") or "").lower() not in allowed:
            return False

    if parsed_filters["doc"]:
        allowed = {item.lower() for item in parsed_filters["doc"]}
        if str(record.get("doc_id") or "").lower() not in allowed:
            return False

    return True
