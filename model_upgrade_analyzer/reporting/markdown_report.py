"""Markdown report writer."""
from __future__ import annotations

from pathlib import Path

from ..models.domain import AnalysisReport, DeploymentImpact, Finding


def _finding_line(f: Finding) -> str:
    ev = ""
    if f.evidence:
        e = f.evidence[0]
        loc = e.file_path + (f":{e.line}" if e.line else "")
        ev = f" _(evidence: `{loc}`)_"
    rec = f" — **Recommendation:** {f.recommendation}" if f.recommendation else ""
    return f"- **[{f.severity.value.upper()} / {f.confidence.value}]** {f.message}{ev}{rec}"


def _impact_section(d: DeploymentImpact) -> str:
    lines: list[str] = []
    lines.append(f"### Deployment: `{d.deployment_name}`")
    lines.append("")
    lines.append(f"- **Current model:** `{d.current_model or 'unknown'}`")
    lines.append(f"- **Target model:** `{d.target_model or 'unknown'}`")
    lines.append(f"- **Deployment type:** {d.deployment_type.value}"
                 + (f" (capacity={d.capacity})" if d.capacity is not None else ""))
    lines.append(f"- **Urgency:** {d.urgency.value}")
    if d.retirement_date:
        lines.append(f"- **Retirement date:** {d.retirement_date.isoformat()}")
    lines.append(f"- **Migration complexity:** {d.migration_complexity}")
    if d.model_card_notes:
        lines.append(f"- **Model card notes:** {d.model_card_notes}")
    if d.parameters_affected:
        lines.append(f"- **Parameters affected:** {', '.join(d.parameters_affected)}")

    if d.code_references:
        lines.append("")
        lines.append("**Code references:**")
        for ref in d.code_references[:25]:
            lines.append(f"  - `{ref.file_path}:{ref.line}` — {ref.reference_kind} = `{ref.value}`")
        if len(d.code_references) > 25:
            lines.append(f"  - …and {len(d.code_references) - 25} more")

    if d.config_references:
        lines.append("")
        lines.append("**Config references:**")
        for ref in d.config_references[:25]:
            lines.append(f"  - `{ref.file_path}:{ref.line}` — {ref.reference_kind} = `{ref.value}`")

    if d.prompt_files:
        lines.append("")
        lines.append("**Prompt files likely affected:**")
        for p in d.prompt_files:
            lines.append(f"  - `{p}`")

    if d.recommended_validation:
        lines.append("")
        lines.append("**Recommended validation steps:**")
        for r in d.recommended_validation:
            lines.append(f"  - {r}")

    if d.findings:
        lines.append("")
        lines.append("**Findings:**")
        for f in d.findings:
            lines.append(_finding_line(f))

    lines.append("")
    return "\n".join(lines)


def write_markdown_report(report: AnalysisReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Model Upgrade Analyzer Report")
    lines.append("")
    lines.append(f"- **Generated:** {report.generated_at}")
    lines.append(f"- **Repo:** `{report.repo_path}`")
    lines.append(f"- **Deployments analyzed:** {len(report.deployments)}")
    lines.append(f"- **Model cards:** {len(report.model_cards)}")
    lines.append(f"- **Code references:** {len(report.code_references)}")
    lines.append(f"- **Prompt observations:** {len(report.prompt_observations)}")
    lines.append(f"- **Findings (global):** {len(report.findings)}")
    lines.append("")

    if report.deployments:
        lines.append("## Deployment Impact")
        lines.append("")
        for d in report.deployments:
            lines.append(_impact_section(d))

    if report.findings:
        lines.append("## Global Findings")
        lines.append("")
        for f in report.findings:
            lines.append(_finding_line(f))
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
