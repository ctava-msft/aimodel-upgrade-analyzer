"""Date parsing helpers tolerant of mixed input formats."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_date(value: Any) -> date | None:
    """Best-effort parse of a date value from strings/datetimes."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    fmts = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%B %d, %Y",
        "%b %d, %Y",
    )
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Fallback: try fromisoformat (handles 2025-01-01 and 2025-01-01T12:00:00)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def days_until(target: date | None, today: date | None = None) -> int | None:
    if target is None:
        return None
    today = today or date.today()
    return (target - today).days
