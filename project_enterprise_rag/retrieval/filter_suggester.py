import re
from collections import Counter
from typing import Iterable, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def normalize_filter_terms(raw_terms: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen = set()

    for term in raw_terms:
        cleaned = re.sub(r"\s+", " ", (term or "").strip().lower())
        cleaned = re.sub(r"[^a-z0-9\s-]", "", cleaned)
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

