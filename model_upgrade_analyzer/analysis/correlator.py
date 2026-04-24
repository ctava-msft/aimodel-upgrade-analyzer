"""Correlate Model IQ records with code refs, prompts, config, and model cards."""
from __future__ import annotations

from pathlib import Path

from ..models.domain import (
    CodeReference,
    DeploymentImpact,
    DeploymentType,
    ModelCard,
    ModelIQRecord,
    PromptObservation,
    Urgency,
)


def _matches(ref: CodeReference, model: str | None, deployment: str | None) -> bool:
    val = (ref.value or "").lower()
    if model and model.lower() in val:
        return True
    if deployment and deployment.lower() in val:
        return True
    return False


def correlate(
    modeliq: list[ModelIQRecord],
    code_refs: list[CodeReference],
    prompt_observations: list[PromptObservation],
    model_cards: list[ModelCard],
) -> list[DeploymentImpact]:
    """Build a DeploymentImpact for each Model IQ record by correlating evidence."""

    cards_by_name = {c.model_name.lower(): c for c in model_cards}
    impacts: list[DeploymentImpact] = []

    for rec in modeliq:
        impact = DeploymentImpact(
            deployment_name=rec.deployment_name or (rec.current_model or "unknown"),
            current_model=rec.current_model,
            target_model=rec.recommended_replacement,
            urgency=rec.urgency if rec.urgency != Urgency.UNKNOWN else Urgency.UNKNOWN,
            deployment_type=rec.deployment_type,
            capacity=rec.capacity,
            retirement_date=rec.retirement_date,
        )

        # Correlate code/config references.
        # Anchor refs: value directly matches the model name or deployment name.
        # Associated refs: live in the same file as an anchor ref (e.g. temperature kwarg
        # next to the model=... call, or a PTU SKU declared in the same Bicep file).
        anchor_refs: list[CodeReference] = [r for r in code_refs
                                             if _matches(r, rec.current_model, rec.deployment_name)]
        anchor_files = {r.file_path for r in anchor_refs}
        matching_refs: list[CodeReference] = list(anchor_refs)
        anchor_ref_ids = {id(r) for r in anchor_refs}
        for ref in code_refs:
            if id(ref) in anchor_ref_ids:
                continue
            if ref.file_path in anchor_files and ref.reference_kind in (
                "deployment_type:ptu", "deployment_type:standard", "deployment_type:batch",
                "deployment_capacity", "endpoint",
            ):
                matching_refs.append(ref)
            elif ref.file_path in anchor_files and ref.reference_kind.startswith(("ast_kwarg:", "param:")):
                matching_refs.append(ref)

        # Split refs into code vs config roughly by path suffix
        for ref in matching_refs:
            suffix = Path(ref.file_path).suffix.lower()
            if suffix in {".json", ".yaml", ".yml", ".env", ".toml", ".ini"}:
                impact.config_references.append(ref)
            else:
                impact.code_references.append(ref)

        # Correlate prompt files — any prompt that references the model or the deployment
        prompt_files: set[str] = set()
        for obs in prompt_observations:
            detail = (obs.detail or "").lower()
            if rec.current_model and rec.current_model.lower() in detail:
                prompt_files.add(obs.file_path)
        # also include prompts that share a directory tree with matching code refs
        code_dirs = {str(Path(r.file_path).parent) for r in matching_refs}
        for obs in prompt_observations:
            if str(Path(obs.file_path).parent) in code_dirs:
                prompt_files.add(obs.file_path)
        impact.prompt_files = sorted(prompt_files)

        # Parameters affected (from ast kwargs + param: refs)
        params: set[str] = set()
        for ref in matching_refs:
            if ref.reference_kind.startswith(("param:", "ast_kwarg:")):
                params.add(ref.reference_kind.split(":", 1)[1])
        impact.parameters_affected = sorted(params)

        # If Model IQ did not provide a deployment type, infer from evidence:
        # any matching deployment_type:ptu ref upgrades impact to PTU.
        if impact.deployment_type == DeploymentType.UNKNOWN:
            for ref in matching_refs:
                if ref.reference_kind == "deployment_type:ptu":
                    impact.deployment_type = DeploymentType.PTU
                    break
                if ref.reference_kind == "deployment_type:batch":
                    impact.deployment_type = DeploymentType.BATCH
                elif ref.reference_kind == "deployment_type:standard" and \
                        impact.deployment_type == DeploymentType.UNKNOWN:
                    impact.deployment_type = DeploymentType.STANDARD

        # Capacity inference from code/config if Model IQ did not provide it.
        if impact.capacity is None:
            for ref in matching_refs:
                if ref.reference_kind == "deployment_capacity":
                    try:
                        impact.capacity = int(ref.value)
                        break
                    except (TypeError, ValueError):
                        continue

        # Model card notes for current model
        card = cards_by_name.get((rec.current_model or "").lower())
        if card is not None:
            impact.model_card_notes = card.migration_notes
            if not impact.target_model and card.replacement:
                impact.target_model = card.replacement
            if not impact.retirement_date and card.retirement_date:
                impact.retirement_date = card.retirement_date

        impacts.append(impact)

    return impacts
