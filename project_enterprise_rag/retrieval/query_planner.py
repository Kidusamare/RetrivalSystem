import re
from typing import Dict, Iterable, List, Optional, Tuple

from planning.llm_planner import generate_query_plan


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


def _normalize_terms(terms: Optional[Iterable[str]]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for term in terms or []:
        value = (term or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def extract_conditional_terms(query: str) -> Tuple[List[str], List[str]]:
    include_terms = re.findall(r"\+([A-Za-z0-9_-]{2,})", query or "")
    exclude_terms = re.findall(r"-([A-Za-z0-9_-]{2,})", query or "")
    return _normalize_terms(include_terms), _normalize_terms(exclude_terms)


def extract_keywords(query: str, max_keywords: int = 10) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9:_-]{3,}", (query or "").lower())
    keywords: List[str] = []
    seen = set()

    for token in tokens:
        token = token.lstrip("+-")
        if token.startswith("source:") or token.startswith("doc:"):
            continue
        if token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def build_planned_query(
    original_query: str,
    keywords: List[str],
    include_terms: Optional[Iterable[str]] = None,
    exclude_terms: Optional[Iterable[str]] = None,
    active_filters: Optional[Iterable[str]] = None,
) -> str:
    parts: List[str] = []
    seen = set()

    def append(value: str) -> None:
        value = (value or "").strip()
        if not value:
            return
        key = value.lower()
        if key in seen:
            return
        seen.add(key)
        parts.append(value)

    append(original_query or "")
    for term in _normalize_terms(include_terms):
        append(f"+{term}")
    for keyword in keywords:
        append(keyword)
    for facet in _normalize_terms(active_filters):
        append(facet)
    for term in _normalize_terms(exclude_terms):
        append(f"-{term}")

    return " ".join(parts).strip()


def _rules_plan(
    *,
    user_query: str,
    mode: str,
    include_terms: List[str],
    exclude_terms: List[str],
    active_filters: List[str],
) -> Dict:
    keywords = extract_keywords(user_query)
    planned_query = build_planned_query(
        original_query=user_query,
        keywords=keywords,
        include_terms=include_terms,
        exclude_terms=exclude_terms,
        active_filters=active_filters,
    )

    return {
        "user_query": user_query,
        "planned_query": planned_query,
        "keywords": keywords,
        "include_terms": include_terms,
        "exclude_terms": exclude_terms,
        "active_filters": active_filters,
        "mode": mode,
        "backend_used": "rules",
        "rationale": "Deterministic plan with extracted keywords and explicit include/exclude constraints.",
    }


def plan_query_mode(
    *,
    user_query: str,
    mode: str = "hybrid",
    planner_backend: str = "rules",
    constraints: Optional[Dict] = None,
    local_llm_config: Optional[Dict] = None,
) -> Dict:
    constraints = constraints or {}
    active_filters = _normalize_terms(constraints.get("active_filters"))
    include_from_query, exclude_from_query = extract_conditional_terms(user_query)
    include_terms = _normalize_terms(list(include_from_query) + list(constraints.get("include_terms") or []))
    exclude_terms = _normalize_terms(list(exclude_from_query) + list(constraints.get("exclude_terms") or []))

    if planner_backend != "local_llm":
        return _rules_plan(
            user_query=user_query,
            mode=mode,
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            active_filters=active_filters,
        )

    config = local_llm_config or {}
    try:
        llm_plan = generate_query_plan(
            user_query=user_query,
            mode=mode,
            constraints={
                "include_terms": include_terms,
                "exclude_terms": exclude_terms,
            },
            base_url=config.get("base_url", "http://127.0.0.1:11434"),
            model=config.get("model", "qwen3:0.6b"),
            timeout_seconds=int(config.get("timeout_seconds", 12)),
        )
        planned_query = build_planned_query(
            original_query=llm_plan["planned_query"],
            keywords=extract_keywords(llm_plan["planned_query"]),
            include_terms=llm_plan.get("include_terms") or include_terms,
            exclude_terms=llm_plan.get("exclude_terms") or exclude_terms,
            active_filters=active_filters,
        )
        keywords = extract_keywords(planned_query)
        return {
            "user_query": user_query,
            "planned_query": planned_query,
            "keywords": keywords,
            "include_terms": _normalize_terms(llm_plan.get("include_terms") or include_terms),
            "exclude_terms": _normalize_terms(llm_plan.get("exclude_terms") or exclude_terms),
            "active_filters": active_filters,
            "mode": mode,
            "backend_used": "local_llm",
            "rationale": llm_plan.get("rationale") or "Local LLM-generated retrieval rewrite.",
        }
    except Exception as exc:  # noqa: BLE001
        fallback = _rules_plan(
            user_query=user_query,
            mode=mode,
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            active_filters=active_filters,
        )
        fallback["backend_used"] = "rules_fallback"
        fallback["rationale"] = f"LLM planner unavailable; using deterministic fallback ({exc})."
        return fallback


def plan_query(user_query: str) -> Dict:
    return plan_query_mode(user_query=user_query, mode="hybrid", planner_backend="rules")
