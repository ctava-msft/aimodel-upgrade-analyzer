"""Risk and urgency scoring for deployments."""
from __future__ import annotations

from datetime import date

from ..models.domain import DeploymentImpact, DeploymentType, Urgency
from ..utils.dates import days_until


def compute_urgency(retirement: date | None, existing: Urgency = Urgency.UNKNOWN) -> Urgency:
    """Combine retirement date and existing urgency into a single bucket."""
    days = days_until(retirement)
    if days is None:
        return existing
    if days <= 0:
        return Urgency.IMMEDIATE
    if days <= 30:
        return Urgency.IMMEDIATE if existing != Urgency.LOW else Urgency.HIGH
    if days <= 90:
        return Urgency.HIGH
    if days <= 180:
        return Urgency.MEDIUM
    return Urgency.LOW if existing == Urgency.UNKNOWN else existing


_COMPLEXITY_ORDER = ["low", "medium", "high"]


def estimate_complexity(impact: DeploymentImpact) -> str:
    """Rough complexity bucket: low / medium / high."""
    score = 0
    score += min(len(impact.code_references), 10)            # per-ref up to 10
    score += 2 * min(len(impact.prompt_files), 5)            # prompts weigh more
    score += 2 * len(impact.parameters_affected)
    score += 3 * len([f for f in impact.findings if f.severity.value in ("high", "critical")])
    # PTU migrations carry additional operational complexity (capacity reservation, cutover).
    if impact.deployment_type == DeploymentType.PTU:
        score += 6

    if score >= 15:
        return "high"
    if score >= 6:
        return "medium"
    return "low"


def worst_complexity(a: str, b: str) -> str:
    try:
        return _COMPLEXITY_ORDER[max(_COMPLEXITY_ORDER.index(a), _COMPLEXITY_ORDER.index(b))]
    except ValueError:
        return a or b or "unknown"
