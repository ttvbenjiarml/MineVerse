from __future__ import annotations

from collections import Counter


def bm25ish_score(query: str, documents: list[str]) -> list[tuple[int, float]]:
    q = query.lower().split()
    results = []
    for index, doc in enumerate(documents):
        words = doc.lower().split()
        counts = Counter(words)
        score = sum(counts[word] for word in q)
        results.append((index, float(score)))
    return sorted(results, key=lambda item: item[1], reverse=True)
