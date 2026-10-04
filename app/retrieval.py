"""Small, dependency-free hybrid runbook retriever (BM25 + sparse TF-IDF cosine)."""

import json
import math
import re
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data" / "runbooks.v1.json"
TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def search(query: str, service: str, limit: int = 3) -> list[tuple[str, str, float]]:
    corpus = json.loads(DATA.read_text(encoding="utf-8"))
    docs = [doc for doc in corpus["documents"] if doc["service"] == service]
    if not docs or not query.strip() or limit <= 0:
        return []

    doc_tokens = [_tokens(f"{doc['title']} {doc['text']}") for doc in docs]
    query_terms = _tokens(query)
    if not query_terms:
        return []
    df = Counter(term for terms in doc_tokens for term in set(terms))
    avg_len = sum(map(len, doc_tokens)) / len(doc_tokens)
    scores: list[tuple[float, dict]] = []
    for doc, terms in zip(docs, doc_tokens):
        counts = Counter(terms)
        bm25 = 0.0
        cosine_dot = 0.0
        doc_norm = 0.0
        query_norm = 0.0
        for term in set(query_terms):
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            freq = counts[term]
            bm25 += idf * freq * 2.2 / (freq + 1.2 * (0.25 + 0.75 * len(terms) / avg_len)) if freq else 0
            weight = (1 + math.log(freq)) * idf if freq else 0
            query_weight = (1 + math.log(query_terms.count(term))) * idf
            cosine_dot += weight * query_weight
            doc_norm += weight * weight
            query_norm += query_weight * query_weight
        cosine = cosine_dot / math.sqrt(doc_norm * query_norm) if doc_norm and query_norm else 0
        scores.append((bm25, {**doc, "cosine": cosine}))

    max_bm25 = max((score for score, _ in scores), default=0) or 1
    ranked = sorted(
        ((0.6 * score / max_bm25 + 0.4 * doc["cosine"], doc) for score, doc in scores),
        key=lambda row: (-row[0], row[1]["id"]),
    )
    return [(doc["id"], doc["title"], round(score, 4)) for score, doc in ranked[:limit] if score > 0]


def retrieve(query: str, service: str) -> tuple[str, str, float] | None:
    results = search(query, service, limit=1)
    return results[0] if results else None
