"""High-level orchestration of impact analysis."""
from __future__ import annotations

from ..models.domain import Confidence, DeploymentImpact, DeploymentType, Evidence, Finding, Severity
from .compatibility_rules import assess_compatibility
from .recommendation_engine import recommendations_for
from .risk_scoring import compute_urgency, estimate_complexity


def enrich_impacts(impacts: list[DeploymentImpact]) -> list[DeploymentImpact]:
    """Populate urgency, complexity, findings, and recommendations on each impact."""
    for impact in impacts:
        impact.urgency = compute_urgency(impact.retirement_date, impact.urgency)

        # PTU-specific finding: provisioned deployments carry capacity/region risk on upgrade.
        if impact.deployment_type == DeploymentType.PTU:
            capacity_text = f" (capacity={impact.capacity})" if impact.capacity is not None else ""
            impact.findings.append(Finding(
                finding_type="ptu_deployment",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                message=(
                    f"Deployment '{impact.deployment_name}' is PTU/provisioned{capacity_text}. "
                    "PTU reservations are model- and region-specific."
                ),
                evidence=[Evidence(
                    file_path=impact.deployment_name,
                    detail=f"deployment_type=ptu; capacity={impact.capacity}",
                )],
                recommendation=(
                    "Before cutover: confirm PTU availability for the replacement model in the target "
                    "region, plan a capacity reservation in parallel, and coordinate quota / commitment "
                    "adjustments with the platform team."
                ),
                tags=["ptu", "capacity", "deployment_type"],
                related_deployment=impact.deployment_name,
                related_model=impact.target_model,
            ))

        verdict = assess_compatibility(impact.current_model, impact.target_model)
        for note in verdict.notes:
            impact.findings.append(Finding(
                finding_type="compatibility_note",
                severity=Severity.MEDIUM if not verdict.compatible else Severity.LOW,
                confidence=Confidence.MEDIUM,
                message=note,
                evidence=[Evidence(
                    file_path=impact.deployment_name,
                    detail=f"{impact.current_model} → {impact.target_model}",
                )],
                recommendation=None,
                tags=["compatibility"],
                related_deployment=impact.deployment_name,
                related_model=impact.target_model,
            ))

        if verdict.likely_parameter_changes:
            for change in verdict.likely_parameter_changes:
                if change not in impact.parameters_affected:
                    impact.parameters_affected.append(change)

        impact.migration_complexity = estimate_complexity(impact)
        impact.recommended_validation = recommendations_for(impact)

        # Per-deployment rollup finding
        impact.findings.append(Finding(
            finding_type="deployment_upgrade_summary",
            severity=_severity_for_urgency(impact.urgency.value),
            confidence=Confidence.MEDIUM,
            message=(
                f"Deployment '{impact.deployment_name}' current={impact.current_model} "
                f"target={impact.target_model} urgency={impact.urgency.value} "
                f"complexity={impact.migration_complexity}"
            ),
            evidence=[Evidence(file_path=impact.deployment_name,
                               detail=f"{len(impact.code_references)} code refs, "
                                      f"{len(impact.prompt_files)} prompt files")],
            recommendation="; ".join(impact.recommended_validation[:3]) or None,
            tags=["summary"],
            related_deployment=impact.deployment_name,
            related_model=impact.target_model,
        ))

    return impacts


def _severity_for_urgency(u: str) -> Severity:
    return {
        "immediate": Severity.CRITICAL,
        "high": Severity.HIGH,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
        "unknown": Severity.INFO,
    }.get(u, Severity.INFO)
