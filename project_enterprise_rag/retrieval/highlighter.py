import html
import re
from typing import Iterable, List


def build_highlight_terms(
    query_keywords: Iterable[str],
    active_filters: Iterable[str],
) -> List[str]:
    combined = list(query_keywords or []) + list(active_filters or [])
    terms: List[str] = []
    seen = set()

    for term in combined:
        clean = (term or "").strip().lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        terms.append(clean)
    return terms


def highlight_text(text: str, terms: Iterable[str]) -> str:
    safe = html.escape(text or "")
    normalized_terms = [t for t in terms if t]
    if not normalized_terms:
        return safe

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(term) for term in normalized_terms) + r")\b",
        flags=re.IGNORECASE,
    )
    return pattern.sub(lambda match: f"<mark>{match.group(0)}</mark>", safe)

