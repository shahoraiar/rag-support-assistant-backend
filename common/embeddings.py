"""Local hashed embeddings (384-d) stored in pgvector."""

from __future__ import annotations

import hashlib
import math
import re

from django.conf import settings

EMBED_DIM = int(getattr(settings, "RAG_EMBED_DIM", 384))

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def embed_text(text: str) -> list[float]:
    """
    Deterministic hashed n-gram embedding (unit-normalized).
    Stored in Postgres via pgvector VectorField.
    """
    vec = [0.0] * EMBED_DIM
    tokens = tokenize(text)
    if not tokens:
        return vec

    grams = list(tokens)
    grams.extend(f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1))
    grams.extend(f"{tokens[i]}_{tokens[i + 1]}_{tokens[i + 2]}" for i in range(len(tokens) - 2))

    for gram in grams:
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        for offset in (0, 4, 8, 12):
            h = int.from_bytes(digest[offset : offset + 4], "big")
            idx = h % EMBED_DIM
            sign = 1.0 if (h & 1) else -1.0
            vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))
