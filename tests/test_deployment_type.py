"""Tests for PTU / non-PTU deployment type handling."""
from __future__ import annotations

import csv
from pathlib import Path

from model_upgrade_analyzer.analysis.correlator import correlate
from model_upgrade_analyzer.analysis.recommendation_engine import recommendations_for
from model_upgrade_analyzer.analysis.risk_scoring import estimate_complexity
from model_upgrade_analyzer.analysis.upgrade_impact import enrich_impacts
from model_upgrade_analyzer.ingest.modeliq_loader import load_modeliq
from model_upgrade_analyzer.models.domain import (
    DeploymentImpact,
    DeploymentType,
    ModelIQRecord,
    Urgency,
)
from model_upgrade_analyzer.scanners.config_scanner import scan_config_file
from model_upgrade_analyzer.scanners.deployment_type import classify_text


def test_classify_text_variants() -> None:
    assert classify_text("ProvisionedManaged") == DeploymentType.PTU
    assert classify_text("GlobalProvisionedManaged") == DeploymentType.PTU
    assert classify_text("DataZoneProvisionedManaged") == DeploymentType.PTU
    assert classify_text("PTU") == DeploymentType.PTU
    assert classify_text("Standard") == DeploymentType.STANDARD
    assert classify_text("GlobalStandard") == DeploymentType.STANDARD
    assert classify_text("PayAsYouGo") == DeploymentType.STANDARD
    assert classify_text("GlobalBatch") == DeploymentType.BATCH
    assert classify_text("") == DeploymentType.UNKNOWN
    assert classify_text(None) == DeploymentType.UNKNOWN


def test_modeliq_loader_parses_ptu_sku(tmp_path: Path) -> None:
    p = tmp_path / "iq.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["deployment", "model", "replacement", "sku", "capacity"])
        writer.writerow(["prod-chat", "gpt-4", "gpt-4o", "ProvisionedManaged", "200"])
        writer.writerow(["dev-chat", "gpt-4", "gpt-4o", "GlobalStandard", ""])
    records = load_modeliq(p)
    assert records[0].deployment_type == DeploymentType.PTU
    assert records[0].capacity == 200
    assert records[1].deployment_type == DeploymentType.STANDARD
    assert records[1].capacity is None


def test_bicep_config_detects_ptu(tmp_path: Path) -> None:
    bicep = tmp_path / "openai.bicep"
    bicep.write_text(
        "resource dep 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {\n"
        "  name: 'prod-chat'\n"
        "  sku: {\n"
        "    name: 'ProvisionedManaged'\n"
        "    capacity: 200\n"
        "  }\n"
        "  properties: {\n"
        "    model: { name: 'gpt-4o' }\n"
        "  }\n"
        "}\n"
    )
    refs, findings = scan_config_file(bicep, tmp_path)
    assert any(r.reference_kind == "deployment_type:ptu" for r in refs)
    assert any(r.reference_kind == "deployment_capacity" and r.value == "200" for r in refs)
    assert any(f.finding_type == "ptu_deployment_config" for f in findings)


def test_ptu_recommendations_and_complexity() -> None:
    impact = DeploymentImpact(
        deployment_name="prod",
        current_model="gpt-4",
        target_model="gpt-4o",
        deployment_type=DeploymentType.PTU,
        capacity=100,
    )
    recs = recommendations_for(impact)
    assert any("PTU" in r for r in recs)
    assert any("blue/green" in r.lower() for r in recs)
    # PTU adds complexity weight
    assert estimate_complexity(impact) in ("medium", "high")


def test_enrich_adds_ptu_finding() -> None:
    rec = ModelIQRecord(
        deployment_name="prod",
        current_model="gpt-4",
        recommended_replacement="gpt-4o",
        sku="ProvisionedManaged",
        deployment_type=DeploymentType.PTU,
        capacity=50,
        urgency=Urgency.HIGH,
    )
    impacts = correlate([rec], [], [], [])
    enriched = enrich_impacts(impacts)
    assert any(f.finding_type == "ptu_deployment" for f in enriched[0].findings)
    assert enriched[0].deployment_type == DeploymentType.PTU


def test_correlator_infers_ptu_from_refs() -> None:
    from model_upgrade_analyzer.models.domain import CodeReference

    rec = ModelIQRecord(deployment_name="prod", current_model="gpt-4",
                        recommended_replacement="gpt-4o")
    refs = [
        CodeReference(file_path="iac/openai.bicep", line=5,
                      reference_kind="deployment_type:ptu", value="ProvisionedManaged"),
        CodeReference(file_path="iac/openai.bicep", line=10,
                      reference_kind="model_name", value="gpt-4"),
    ]
    impacts = correlate([rec], refs, [], [])
    assert impacts[0].deployment_type == DeploymentType.PTU
