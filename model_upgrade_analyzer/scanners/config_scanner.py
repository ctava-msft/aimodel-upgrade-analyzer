"""Config file scanner (JSON, YAML, env, toml, ini)."""
from __future__ import annotations

from pathlib import Path

from ..models.domain import CodeReference, Confidence, Evidence, Finding, Severity
from ..utils.files import read_text, relative_path
from ..utils.text import truncate
from . import pattern_library as P
from .deployment_type import (
    CAPACITY_KEY_PATTERN,
    scan_text_for_deployment_types,
)


def scan_config_file(path: Path, root: Path) -> tuple[list[CodeReference], list[Finding]]:
    text = read_text(path)
    if not text:
        return [], []
    rel = relative_path(path, root)
    refs: list[CodeReference] = []
    findings: list[Finding] = []
    lines = text.splitlines()

    # Model names
    for model_name, match in P.find_model_names(text):
        line_no = text.count("\n", 0, match.start()) + 1
        snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
        refs.append(CodeReference(
            file_path=rel, line=line_no, reference_kind="model_name",
            value=model_name, context=truncate(snippet or "", 200) if snippet else None,
        ))
        findings.append(Finding(
            finding_type="config_model_reference",
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            message=f"Config references model '{model_name}'",
            evidence=[Evidence(file_path=rel, line=line_no, snippet=snippet)],
            recommendation="Update config on rollout; ensure environment-specific overrides are handled.",
            tags=["config", "model_reference"],
            related_model=model_name,
        ))

    # Deployment / endpoint
    for pat in P.DEPLOYMENT_PATTERNS + P.ENDPOINT_PATTERNS:
        for m in pat.finditer(text):
            value = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1) if m.groups() else m.group(0)
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
            kind = "endpoint" if "endpoint" in m.group(0).lower() or "openai.azure.com" in (value or "") \
                else "deployment_name"
            refs.append(CodeReference(
                file_path=rel, line=line_no, reference_kind=kind,
                value=value, context=truncate(snippet or "", 200) if snippet else None,
            ))

    # Deployment type (PTU / Standard / Batch) in IaC configs.
    for dtype, m in scan_text_for_deployment_types(text):
        line_no = text.count("\n", 0, m.start()) + 1
        snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
        value = m.group(m.lastindex) if m.lastindex else m.group(0)
        refs.append(CodeReference(
            file_path=rel, line=line_no,
            reference_kind=f"deployment_type:{dtype.value}",
            value=(value or "").strip(),
            context=truncate(snippet or "", 200) if snippet else None,
        ))
        if dtype.value == "ptu":
            findings.append(Finding(
                finding_type="ptu_deployment_config",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                message="PTU (provisioned) deployment SKU declared in configuration.",
                evidence=[Evidence(file_path=rel, line=line_no, snippet=snippet)],
                recommendation=(
                    "Verify PTU capacity is available for the replacement model in the target region "
                    "before cutover; PTU reservations do not automatically transfer across models."
                ),
                tags=["config", "ptu", "capacity"],
            ))

    # Capacity / PTU count
    for m in CAPACITY_KEY_PATTERN.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
        refs.append(CodeReference(
            file_path=rel, line=line_no,
            reference_kind="deployment_capacity",
            value=m.group(2),
            context=truncate(snippet or "", 200) if snippet else None,
        ))

    return refs, findings


def scan_configs(files: list[Path], root: Path) -> tuple[list[CodeReference], list[Finding]]:
    refs: list[CodeReference] = []
    findings: list[Finding] = []
    for path in files:
        r, f = scan_config_file(path, root)
        refs.extend(r)
        findings.extend(f)
    return refs, findings
