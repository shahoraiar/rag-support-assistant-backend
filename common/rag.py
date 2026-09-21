"""pgvector RAG over knowledge PDF chunks."""

from __future__ import annotations

import re

from django.conf import settings
from pgvector.django import CosineDistance

from common.embeddings import embed_text, tokenize
from knowledgesu.choices import DocStatus
from knowledgesu.models import DocumentChunk


def _min_score() -> float:
    return float(getattr(settings, "RAG_MIN_SCORE", 0.32))


_STOPWORDS = {
    "who", "what", "when", "where", "which", "how", "why",
    "is", "are", "was", "were", "the", "a", "an", "and", "or", "to", "of",
    "in", "on", "for", "my", "your", "our", "me", "you", "we", "do", "does",
    "can", "with", "from", "about", "please", "give", "tell", "information",
    "that", "this", "have", "has", "will", "be", "by", "as", "it", "its",
}


def _normalize(text: str) -> str:
    t = (text or "").lower().replace("‑", "-").replace("–", "-")
    t = t.replace("wi-fi", "wifi").replace("wi fi", "wifi")
    return re.sub(r"[^a-z0-9\s]+", " ", t)


def _query_terms(query: str) -> set[str]:
    return {
        w
        for w in tokenize(_normalize(query))
        if len(w) > 2 and w not in _STOPWORDS
    }


def _keyword_overlap(query: str, content: str) -> float:
    q_tokens = _query_terms(query)
    if not q_tokens:
        return 0.0
    c_tokens = set(tokenize(_normalize(content)))
    hit = len(q_tokens & c_tokens)
    base = hit / max(len(q_tokens), 1)
    distinctive = {
        "router", "wifi", "refund", "grace", "privacy", "suspend", "suspension",
        "reconnect", "invoice", "billing", "payment", "equipment", "installation",
        "activation", "personal", "data", "collect",
    }
    key_terms = q_tokens & distinctive
    if key_terms:
        key_hits = len(key_terms & c_tokens)
        key_ratio = key_hits / len(key_terms)
        return min(1.0, 0.35 * base + 0.65 * key_ratio)
    return min(1.0, base)


def retrieve_knowledge(
    query: str,
    *,
    limit: int | None = None,
    min_score: float | None = None,
) -> tuple[str, list[dict], bool]:
    """
    pgvector cosine search over embedded PDF chunks.

    Returns:
        context, sources, has_match
    """
    limit = limit or int(getattr(settings, "RAG_TOP_K", 4))
    threshold = _min_score() if min_score is None else min_score
    query = (query or "").strip()
    if not query:
        return "", [], False

    q_emb = embed_text(query)

    # Fetch a wider candidate set from Postgres (ANN / exact cosine via pgvector)
    fetch_n = max(limit * 8, 24)
    qs = (
        DocumentChunk.objects.filter(document__status=DocStatus.READY, embedding__isnull=False)
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", q_emb))
        .order_by("distance")[:fetch_n]
    )

    scored: list[tuple[float, float, DocumentChunk]] = []
    for chunk in qs:
        # CosineDistance = 1 - cosine_similarity for unit vectors
        distance = float(chunk.distance or 1.0)
        vec_score = max(0.0, 1.0 - distance)
        kw = _keyword_overlap(query, chunk.content or "")
        score = vec_score + 0.35 * kw
        scored.append((score, kw, chunk))

    # Lazy-embed any READY chunks still missing vectors
    if not scored:
        legacy = (
            DocumentChunk.objects.filter(document__status=DocStatus.READY, embedding__isnull=True)
            .select_related("document")[:200]
        )
        for chunk in legacy:
            emb = embed_text(chunk.content or "")
            chunk.embedding = emb
            chunk.save(update_fields=["embedding", "updated_at"])
            from common.embeddings import cosine_similarity

            vec_score = cosine_similarity(q_emb, emb)
            kw = _keyword_overlap(query, chunk.content or "")
            scored.append((vec_score + 0.35 * kw, kw, chunk))

    scored.sort(key=lambda row: (row[1], row[0]), reverse=True)

    strong = threshold + 0.12
    candidates: list[tuple[float, float, DocumentChunk]] = []
    for score, kw, chunk in scored:
        if score < threshold:
            continue
        if kw < 0.08 and score < strong:
            continue
        candidates.append((score, kw, chunk))

    if not candidates:
        return "", [], False

    best_by_title: dict[str, tuple[float, float, DocumentChunk]] = {}
    for score, kw, chunk in candidates:
        title = chunk.document.title
        prev = best_by_title.get(title)
        if prev is None or (kw, score) > (prev[1], prev[0]):
            best_by_title[title] = (score, kw, chunk)

    ranked = sorted(best_by_title.values(), key=lambda row: (row[1], row[0]), reverse=True)
    if ranked:
        top_kw = ranked[0][1]
        floor = max(0.35, top_kw - 0.2)
        filtered = [row for row in ranked if row[1] >= floor]
        ranked = (filtered or ranked[:1])[: min(limit, 2)]
    else:
        ranked = []

    sources = [
        {
            "title": chunk.document.title,
            "snippet": (chunk.content or "").strip()[:180],
            "score": round(score, 4),
        }
        for score, _kw, chunk in ranked
    ]
    context = "\n\n---\n\n".join(
        f"Reference: {chunk.document.title}\n{chunk.content}" for _s, _k, chunk in ranked
    )
    return context, sources, True
