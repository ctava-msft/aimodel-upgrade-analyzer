"""JSON report writer."""
from __future__ import annotations

import json
from pathlib import Path

from ..models.domain import AnalysisReport


def write_json_report(report: AnalysisReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
    return out_path
