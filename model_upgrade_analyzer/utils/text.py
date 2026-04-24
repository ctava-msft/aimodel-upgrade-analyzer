"""Text helpers."""
from __future__ import annotations

import re


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_key(key: str) -> str:
    """Normalize a column/field key for fuzzy matching."""
    return _WHITESPACE_RE.sub("_", key.strip().lower()).replace("-", "_")


def truncate(text: str, limit: int = 240) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def count_tokens_approx(text: str) -> int:
    """Rough token estimate (~4 chars/token). Good enough for heuristics."""
    return max(1, len(text) // 4)
