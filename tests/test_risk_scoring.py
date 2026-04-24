"""Tests for urgency and complexity scoring."""
from __future__ import annotations

from datetime import date, timedelta

from model_upgrade_analyzer.analysis.risk_scoring import compute_urgency, estimate_complexity
from model_upgrade_analyzer.models.domain import (
    CodeReference,
    DeploymentImpact,
    Finding,
    Severity,
    Confidence,
    Urgency,
)


def test_urgency_buckets() -> None:
    today = date.today()
    assert compute_urgency(today - timedelta(days=1)) == Urgency.IMMEDIATE
    assert compute_urgency(today + timedelta(days=10)) in (Urgency.IMMEDIATE, Urgency.HIGH)
    assert compute_urgency(today + timedelta(days=60)) == Urgency.HIGH
    assert compute_urgency(today + timedelta(days=150)) == Urgency.MEDIUM
    assert compute_urgency(today + timedelta(days=365)) in (Urgency.LOW, Urgency.UNKNOWN)


def test_complexity_low() -> None:
    impact = DeploymentImpact(deployment_name="d")
    assert estimate_complexity(impact) == "low"


def test_complexity_high() -> None:
    impact = DeploymentImpact(
        deployment_name="d",
        code_references=[CodeReference(file_path=f"f{i}.py", line=i, reference_kind="model_name", value="gpt-4")
                          for i in range(12)],
        prompt_files=[f"p{i}.md" for i in range(5)],
        parameters_affected=["temperature", "max_tokens", "response_format"],
        findings=[Finding(finding_type="x", severity=Severity.HIGH, confidence=Confidence.HIGH, message="m")
                  for _ in range(3)],
    )
    assert estimate_complexity(impact) == "high"
