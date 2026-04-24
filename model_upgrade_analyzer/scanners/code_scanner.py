"""Source-code scanner producing CodeReference records and Findings."""
from __future__ import annotations

from pathlib import Path

from ..config import AnalyzerConfig
from ..models.domain import CodeReference, Confidence, Evidence, Finding, Severity
from ..utils.files import read_text, relative_path
from ..utils.text import truncate
from . import pattern_library as P
from .ast_helpers import extract_python_call_kwargs
from .deployment_type import scan_text_for_deployment_types


_AST_KWARGS = {
    "model", "deployment", "deployment_name", "azure_deployment",
    "temperature", "top_p", "max_tokens", "max_completion_tokens",
    "reasoning_effort", "response_format", "stream", "tools", "tool_choice",
}


def scan_code_file(path: Path, root: Path) -> tuple[list[CodeReference], list[Finding]]:
    text = read_text(path)
    if not text:
        return [], []
    rel = relative_path(path, root)
    refs: list[CodeReference] = []
    findings: list[Finding] = []

    # --- Model name references ---
    lines = text.splitlines()
    for model_name, match in P.find_model_names(text):
        line_no = text.count("\n", 0, match.start()) + 1
        snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
        refs.append(CodeReference(
            file_path=rel,
            line=line_no,
            reference_kind="model_name",
            value=model_name,
            context=truncate(snippet or "", 200) if snippet else None,
        ))
        severity = Severity.HIGH if model_name.lower() in P.DEPRECATED_MODELS else Severity.MEDIUM
        findings.append(Finding(
            finding_type="hardcoded_model_reference",
            severity=severity,
            confidence=Confidence.HIGH,
            message=f"Hard-coded model reference '{model_name}'",
            evidence=[Evidence(file_path=rel, line=line_no, snippet=snippet)],
            recommendation=(
                "Replace with a config-driven or mapped model reference so future "
                "upgrades do not require code changes."
            ),
            tags=["code", "model_reference"],
            related_model=model_name,
        ))

    # --- Deployment / endpoint references ---
    for pat in P.DEPLOYMENT_PATTERNS:
        for m in pat.finditer(text):
            value = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
            # skip generic "model": "..." matches that already got captured as a model name
            if any(r.value == value and r.reference_kind == "model_name" for r in refs):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
            refs.append(CodeReference(
                file_path=rel, line=line_no, reference_kind="deployment_name",
                value=value, context=truncate(snippet or "", 200) if snippet else None,
            ))

    for pat in P.ENDPOINT_PATTERNS:
        for m in pat.finditer(text):
            value = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(0)
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
            refs.append(CodeReference(
                file_path=rel, line=line_no, reference_kind="endpoint",
                value=value, context=truncate(snippet or "", 200) if snippet else None,
            ))

    # --- SDK / client usage findings ---
    for sdk_kind, pat in P.SDK_PATTERNS.items():
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
            findings.append(Finding(
                finding_type="sdk_usage",
                severity=Severity.INFO,
                confidence=Confidence.HIGH,
                message=f"Detected SDK usage: {sdk_kind}",
                evidence=[Evidence(file_path=rel, line=line_no, snippet=snippet)],
                recommendation=None,
                tags=["code", "sdk", sdk_kind],
            ))

    # --- Inference parameters (regex) ---
    for param, pat in P.PARAM_PATTERNS.items():
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
            refs.append(CodeReference(
                file_path=rel, line=line_no, reference_kind=f"param:{param}",
                value=m.group(0), context=truncate(snippet or "", 200) if snippet else None,
            ))

    # --- Python AST pass for stronger evidence on kwargs ---
    if path.suffix.lower() == ".py":
        for hit in extract_python_call_kwargs(text, _AST_KWARGS):
            snippet = lines[hit.line - 1] if 0 < hit.line <= len(lines) else None
            refs.append(CodeReference(
                file_path=rel,
                line=hit.line,
                reference_kind=f"ast_kwarg:{hit.kwarg}",
                value=f"{hit.call_name}({hit.kwarg}={hit.value})",
                context=truncate(snippet or "", 200) if snippet else None,
            ))

    # --- Deployment type (PTU / Standard / Batch) ---
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
                finding_type="ptu_deployment_reference",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                message="Code references a PTU (provisioned) deployment SKU.",
                evidence=[Evidence(file_path=rel, line=line_no, snippet=snippet)],
                recommendation=(
                    "PTU reservations are model-specific. Confirm PTU availability for the "
                    "replacement model in the same region before migration."
                ),
                tags=["code", "ptu", "capacity"],
            ))

    return refs, findings


def scan_code(files: list[Path], config: AnalyzerConfig) -> tuple[list[CodeReference], list[Finding]]:
    all_refs: list[CodeReference] = []
    all_findings: list[Finding] = []
    for path in files:
        refs, findings = scan_code_file(path, config.repo_path)
        all_refs.extend(refs)
        all_findings.extend(findings)
    return all_refs, all_findings
