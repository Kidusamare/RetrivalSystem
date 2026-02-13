import re
from typing import Dict, List


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def extract_keywords(query: str, max_keywords: int = 10) -> List[str]:
    terms = re.findall(r"[A-Za-z0-9]{3,}", (query or "").lower())
    keywords: List[str] = []
    seen = set()

    for term in terms:
        if term in STOPWORDS or term in seen:
            continue
        seen.add(term)
        keywords.append(term)
        if len(keywords) >= max_keywords:
            break
    return keywords


def build_planned_query(original_query: str, keywords: List[str]) -> str:
    base = (original_query or "").strip()
    if not keywords:
        return base
    return f"{base} {' '.join(keywords)}".strip()


def plan_query(user_query: str) -> Dict:
    keywords = extract_keywords(user_query)
    planned_query = build_planned_query(user_query, keywords)
    rationale = "Expanded query with deterministic keywords for stable local retrieval."
    return {
        "user_query": user_query,
        "planned_query": planned_query,
        "keywords": keywords,
        "rationale": rationale,
    }

