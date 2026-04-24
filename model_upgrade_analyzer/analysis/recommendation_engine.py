"""Recommendation engine: validation and migration steps per deployment."""
from __future__ import annotations

from ..models.domain import DeploymentImpact, DeploymentType
from .compatibility_rules import assess_compatibility


def recommendations_for(impact: DeploymentImpact) -> list[str]:
    """Return a list of actionable validation/migration steps."""
    recs: list[str] = []
    verdict = assess_compatibility(impact.current_model, impact.target_model)

    recs.append("Run full regression on representative prompts using the target model.")
    recs.append("Capture golden outputs before cutover and diff against post-cutover responses.")

    if impact.deployment_type == DeploymentType.PTU:
        capacity_hint = f" (currently {impact.capacity} PTU)" if impact.capacity else ""
        recs.append(
            f"PTU deployment{capacity_hint}: verify PTU availability and pricing for the replacement "
            "model in the target region; reserve capacity in parallel before cutover."
        )
        recs.append(
            "Plan a blue/green PTU switchover: keep the current PTU deployment live until the new "
            "deployment passes validation, then drain traffic and release the old reservation."
        )
        recs.append("Re-run load/throughput tests against the new PTU deployment to confirm TPM/RPM sizing.")
    elif impact.deployment_type == DeploymentType.STANDARD:
        recs.append(
            "Standard (pay-as-you-go) deployment: confirm target model is available in the region "
            "and verify per-token pricing and rate-limit (TPM/RPM) quotas."
        )
    elif impact.deployment_type == DeploymentType.BATCH:
        recs.append(
            "Batch deployment: validate that the replacement model supports batch jobs and re-run "
            "a sample batch to confirm output schema and latency."
        )

    if impact.prompt_files:
        recs.append("Re-evaluate prompt templates; focus on formatting, JSON strictness, and few-shot examples.")
    if any("json" in p.lower() for p in impact.parameters_affected) or \
       any(f.finding_type == "strict_json_output_expectation" for f in impact.findings):
        recs.append("Validate structured output / JSON mode support on the target model.")
    if any(f.finding_type == "token_heavy_prompt" for f in impact.findings):
        recs.append("Confirm target model context window and adjust truncation/summarization strategy.")
    if verdict.likely_parameter_changes:
        recs.append("Update inference parameters: " + "; ".join(verdict.likely_parameter_changes) + ".")
    if any(r.reference_kind == "model_name" for r in impact.code_references):
        recs.append("Move hard-coded model names to config; keep a mapping table for rollouts and rollback.")
    if impact.urgency.value in ("high", "immediate"):
        recs.append("Schedule migration immediately; coordinate with platform team on deployment windows.")

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique
