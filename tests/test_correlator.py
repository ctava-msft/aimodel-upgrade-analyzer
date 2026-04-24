"""Tests for the correlator."""
from __future__ import annotations

from datetime import date

from model_upgrade_analyzer.analysis.correlator import correlate
from model_upgrade_analyzer.models.domain import (
    CodeReference,
    ModelCard,
    ModelIQRecord,
    PromptObservation,
    Urgency,
)


def test_correlates_code_and_prompt() -> None:
    rec = ModelIQRecord(
        deployment_name="prod-chat",
        current_model="gpt-4",
        recommended_replacement="gpt-4o",
        retirement_date=date(2026, 12, 1),
        urgency=Urgency.HIGH,
    )
    refs = [
        CodeReference(file_path="src/app.py", line=10, reference_kind="model_name", value="gpt-4"),
        CodeReference(file_path="config/app.json", line=3, reference_kind="model_name", value="gpt-4"),
        CodeReference(file_path="src/other.py", line=4, reference_kind="model_name", value="claude-3"),
        CodeReference(file_path="src/app.py", line=12, reference_kind="ast_kwarg:temperature", value="0.2"),
    ]
    obs = [
        PromptObservation(file_path="src/prompts/system.md", trait="strict_json",
                          detail="respond only in json for gpt-4"),
    ]
    cards = [ModelCard(model_name="gpt-4", replacement="gpt-4o",
                       retirement_date=date(2026, 12, 1), migration_notes="Move to gpt-4o")]

    impacts = correlate([rec], refs, obs, cards)
    assert len(impacts) == 1
    i = impacts[0]
    assert i.deployment_name == "prod-chat"
    assert any(r.file_path == "src/app.py" for r in i.code_references)
    assert any(r.file_path == "config/app.json" for r in i.config_references)
    assert "src/prompts/system.md" in i.prompt_files
    assert "temperature" in i.parameters_affected
    assert i.model_card_notes == "Move to gpt-4o"
