"""Command-line entry point for Model Upgrade Analyzer."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .analysis.correlator import correlate
from .analysis.upgrade_impact import enrich_impacts
from .config import AnalyzerConfig
from .ingest.model_card_loader import load_model_cards
from .ingest.modeliq_loader import load_modeliq
from .ingest.repo_inventory import build_inventory
from .models.domain import AnalysisReport
from .reporting.html_report import write_html_report
from .reporting.json_report import write_json_report
from .reporting.markdown_report import write_markdown_report
from .scanners.code_scanner import scan_code
from .scanners.config_scanner import scan_configs
from .scanners.prompt_scanner import scan_prompts
from .utils.logging import get_logger


log = get_logger()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="model-upgrade-analyzer",
        description="Analyze Azure AI / LLM model upgrades across code, prompts, configs, and Model IQ data.",
    )
    p.add_argument("--repo", required=True, type=Path, help="Repository path to analyze.")
    p.add_argument("--modeliq", type=Path, default=None, help="Model IQ export (json/csv/xlsx/yaml).")
    p.add_argument("--model-cards", type=Path, default=None, help="Model cards directory or file.")
    p.add_argument("--output", type=Path, default=Path("reports"), help="Output directory for reports.")
    p.add_argument(
        "--format",
        default="json,md",
        help="Comma-separated report formats: json, md, html, pptx. Default: json,md",
    )
    return p.parse_args(argv)


def run(config: AnalyzerConfig) -> AnalysisReport:
    log.info("Building repo inventory: %s", config.repo_path)
    inv = build_inventory(config)
    log.info("  code=%d prompts=%d config=%d", len(inv.code_files), len(inv.prompt_files), len(inv.config_files))

    log.info("Scanning source code…")
    code_refs, code_findings = scan_code(inv.code_files, config)

    log.info("Scanning prompt files…")
    prompt_obs, prompt_findings = scan_prompts(inv.prompt_files, config.repo_path)

    log.info("Scanning config files…")
    config_refs, config_findings = scan_configs(inv.config_files, config.repo_path)

    modeliq_records = []
    if config.modeliq_path:
        log.info("Loading Model IQ: %s", config.modeliq_path)
        modeliq_records = load_modeliq(config.modeliq_path)

    model_cards = []
    if config.model_cards_path:
        log.info("Loading model cards: %s", config.model_cards_path)
        model_cards = load_model_cards(config.model_cards_path)

    log.info("Correlating deployments with evidence…")
    impacts = correlate(
        modeliq_records,
        code_refs + config_refs,
        prompt_obs,
        model_cards,
    )
    impacts = enrich_impacts(impacts)

    report = AnalysisReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        repo_path=str(config.repo_path),
        modeliq_records=modeliq_records,
        model_cards=model_cards,
        code_references=code_refs + config_refs,
        prompt_observations=prompt_obs,
        findings=code_findings + prompt_findings + config_findings,
        deployments=impacts,
    )
    return report


def _write_reports(report: AnalysisReport, config: AnalyzerConfig) -> list[Path]:
    out: list[Path] = []
    out_dir = config.output_dir
    for fmt in config.formats:
        fmt = fmt.strip().lower()
        if fmt == "json":
            out.append(write_json_report(report, out_dir / "report.json"))
        elif fmt in ("md", "markdown"):
            out.append(write_markdown_report(report, out_dir / "report.md"))
        elif fmt == "html":
            out.append(write_html_report(report, out_dir / "report.html"))
        elif fmt == "pptx":
            from .reporting.pptx_export import write_pptx_report  # optional import
            out.append(write_pptx_report(report, out_dir / "report.pptx"))
        else:
            log.warning("Unknown format: %s (skipped)", fmt)
    return out


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    config = AnalyzerConfig(
        repo_path=args.repo.resolve(),
        modeliq_path=args.modeliq.resolve() if args.modeliq else None,
        model_cards_path=args.model_cards.resolve() if args.model_cards else None,
        output_dir=args.output.resolve(),
        formats=tuple(s.strip() for s in args.format.split(",") if s.strip()),
    )

    if not config.repo_path.exists():
        log.error("Repo path does not exist: %s", config.repo_path)
        return 2

    report = run(config)
    written = _write_reports(report, config)
    for p in written:
        log.info("Wrote %s", p)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
