import re
from collections import Counter
from typing import Dict, Iterable, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def normalize_filter_terms(raw_terms: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen = set()

    for term in raw_terms:
        cleaned = re.sub(r"\s+", " ", (term or "").strip().lower())
        cleaned = re.sub(r"[^a-z0-9\s:_-]", "", cleaned)
        if len(cleaned) < 3 or cleaned.isdigit() or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _fallback_frequency_terms(texts: List[str], top_k: int) -> List[str]:
    tokens = []
    for text in texts:
        tokens.extend(re.findall(r"[A-Za-z0-9]{3,}", text.lower()))
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(top_k)]


def suggest_filters(
    chunks: Iterable[dict],
    query_terms: Iterable[str],
    top_k: int = 8,
) -> List[str]:
    texts = [chunk.get("text", "") for chunk in chunks if chunk.get("text")]
    if not texts:
        return []

    query_term_set = set(normalize_filter_terms(query_terms))

    try:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=300)
        matrix = vectorizer.fit_transform(texts)
        scores = np.asarray(matrix.mean(axis=0)).ravel()
        terms = vectorizer.get_feature_names_out()
        ranked_terms = [terms[i] for i in np.argsort(scores)[::-1]]
    except ValueError:
        ranked_terms = _fallback_frequency_terms(texts, top_k=top_k * 2)

    normalized = normalize_filter_terms(ranked_terms)
    suggestions: List[str] = []

    for term in normalized:
        if term in query_term_set:
            continue
        if term not in suggestions:
            suggestions.append(term)
        if len(suggestions) >= top_k:
            break

    return suggestions


def _count_term_presence(texts: List[str], terms: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    lowered_texts = [text.lower() for text in texts]

    for term in terms:
        token = term.lower()
        counts[term] = sum(1 for text in lowered_texts if token in text)

    return counts


def _counter_to_facet_rows(counter: Counter, prefix: str = "", top_k: int = 10) -> List[Dict]:
    rows: List[Dict] = []
    for value, count in counter.most_common(top_k):
        cleaned_value = (value or "").strip()
        if not cleaned_value:
            continue
        token = f"{prefix}{cleaned_value}" if prefix else cleaned_value
        rows.append(
            {
                "token": token,
                "label": cleaned_value,
                "count": int(count),
            }
        )
    return rows


def build_facets(
    chunks: Iterable[dict],
    query_terms: Iterable[str],
    top_term_k: int = 8,
    top_value_k: int = 10,
) -> Dict[str, List[Dict]]:
    chunk_list = list(chunks or [])
    texts = [chunk.get("text", "") for chunk in chunk_list if chunk.get("text")]

    term_tokens = suggest_filters(chunk_list, query_terms=query_terms, top_k=top_term_k)
    term_counts = _count_term_presence(texts=texts, terms=term_tokens)

    term_rows = [
        {
            "token": token,
            "label": token,
            "count": int(term_counts.get(token, 0)),
        }
        for token in term_tokens
    ]

    source_counter = Counter(
        (chunk.get("source") or "Unknown")
        for chunk in chunk_list
        if (chunk.get("source") or "").strip()
    )
    doc_counter = Counter(
        str(chunk.get("doc_id") or "unknown")
        for chunk in chunk_list
        if str(chunk.get("doc_id") or "").strip()
    )

    source_rows = _counter_to_facet_rows(source_counter, prefix="source:", top_k=top_value_k)
    doc_rows = _counter_to_facet_rows(doc_counter, prefix="doc:", top_k=top_value_k)

    return {
        "term": term_rows,
        "source_file": source_rows,
        "doc_id": doc_rows,
    }
