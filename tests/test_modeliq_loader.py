"""Tests for Model IQ loader."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from model_upgrade_analyzer.ingest.modeliq_loader import load_modeliq
from model_upgrade_analyzer.models.domain import Urgency


def test_load_json(tmp_path: Path) -> None:
    p = tmp_path / "iq.json"
    p.write_text(json.dumps([
        {
            "Deployment Name": "prod-chat",
            "Current Model": "gpt-4",
            "Recommended Replacement": "gpt-4o",
            "Retirement Date": "2026-06-30",
            "Urgency": "High",
            "Region": "eastus",
        }
    ]))
    records = load_modeliq(p)
    assert len(records) == 1
    r = records[0]
    assert r.deployment_name == "prod-chat"
    assert r.current_model == "gpt-4"
    assert r.recommended_replacement == "gpt-4o"
    assert r.urgency == Urgency.HIGH
    assert r.retirement_date is not None and r.retirement_date.isoformat() == "2026-06-30"


def test_load_csv(tmp_path: Path) -> None:
    p = tmp_path / "iq.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["deployment", "model", "replacement", "urgency"])
        writer.writerow(["d1", "gpt-3.5-turbo", "gpt-4o-mini", "medium"])
    records = load_modeliq(p)
    assert len(records) == 1
    assert records[0].current_model == "gpt-3.5-turbo"
    assert records[0].urgency == Urgency.MEDIUM


def test_load_yaml(tmp_path: Path) -> None:
    p = tmp_path / "iq.yaml"
    p.write_text(
        "records:\n"
        "  - deployment: d1\n"
        "    model: gpt-4\n"
        "    replacement: gpt-4o\n"
        "    urgency: immediate\n",
    )
    records = load_modeliq(p)
    assert len(records) == 1
    assert records[0].urgency == Urgency.IMMEDIATE
