"""Prompt-file scanner producing PromptObservation records and Findings."""
from __future__ import annotations

from pathlib import Path

from ..models.domain import Confidence, Evidence, Finding, PromptObservation, Severity
from ..utils.files import read_text, relative_path
from ..utils.text import count_tokens_approx, truncate
from . import pattern_library as P


TOKEN_HEAVY_THRESHOLD = 1500  # ~tokens
FEW_SHOT_MIN = 2


def scan_prompt_file(path: Path, root: Path) -> tuple[list[PromptObservation], list[Finding]]:
    text = read_text(path)
    if not text.strip():
        return [], []
    rel = relative_path(path, root)
    observations: list[PromptObservation] = []
    findings: list[Finding] = []
    lines = text.splitlines()

    for trait, pat in P.PROMPT_TRAIT_PATTERNS.items():
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else None
            observations.append(PromptObservation(
                file_path=rel, trait=trait,
                detail=truncate(snippet or m.group(0), 200),
                line=line_no,
            ))

    # Token-heavy
    tokens = count_tokens_approx(text)
    if tokens >= TOKEN_HEAVY_THRESHOLD:
        observations.append(PromptObservation(
            file_path=rel, trait="token_heavy", detail=f"approx {tokens} tokens",
        ))
        findings.append(Finding(
            finding_type="token_heavy_prompt",
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            message=f"Prompt is token-heavy (~{tokens} tokens); context window changes may matter on upgrade.",
            evidence=[Evidence(file_path=rel, detail=f"~{tokens} tokens")],
            recommendation="Verify target model's context window and output budget.",
            tags=["prompt", "size"],
        ))

    # Few-shot (count example markers)
    few_shot_matches = list(P.PROMPT_TRAIT_PATTERNS["few_shot"].finditer(text))
    if len(few_shot_matches) >= FEW_SHOT_MIN:
        findings.append(Finding(
            finding_type="brittle_few_shot",
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            message="Few-shot examples detected; newer models may require different example structure.",
            evidence=[Evidence(file_path=rel,
                               line=text.count("\n", 0, few_shot_matches[0].start()) + 1)],
            recommendation="Re-evaluate few-shot examples after upgrade; consider reducing or restructuring.",
            tags=["prompt", "few_shot"],
        ))

    # Deprecated model references in prompts
    for m in P.PROMPT_TRAIT_PATTERNS["deprecated_model_reference"].finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        findings.append(Finding(
            finding_type="deprecated_model_in_prompt",
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            message=f"Prompt references deprecated model '{m.group(1)}'.",
            evidence=[Evidence(file_path=rel, line=line_no, snippet=lines[line_no - 1]
                               if 0 < line_no <= len(lines) else None)],
            recommendation="Remove or update the deprecated model mention in the prompt.",
            tags=["prompt", "deprecated"],
            related_model=m.group(1),
        ))

    # Strict JSON expectations
    if P.PROMPT_TRAIT_PATTERNS["strict_json"].search(text):
        findings.append(Finding(
            finding_type="strict_json_output_expectation",
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            message="Prompt expects strict JSON output.",
            evidence=[Evidence(file_path=rel)],
            recommendation=(
                "Confirm target model supports structured output / JSON mode, "
                "or add schema-enforced response_format."
            ),
            tags=["prompt", "json"],
        ))

    # Chain-of-thought hints
    if P.PROMPT_TRAIT_PATTERNS["chain_of_thought"].search(text):
        findings.append(Finding(
            finding_type="chain_of_thought_prompt",
            severity=Severity.LOW,
            confidence=Confidence.MEDIUM,
            message="Prompt uses chain-of-thought / explicit reasoning instructions.",
            evidence=[Evidence(file_path=rel)],
            recommendation=(
                "Reasoning-native models (o-series) may not need CoT prompting; "
                "review for redundancy or conflicting instructions."
            ),
            tags=["prompt", "reasoning"],
        ))

    return observations, findings


def scan_prompts(files: list[Path], root: Path) -> tuple[list[PromptObservation], list[Finding]]:
    observations: list[PromptObservation] = []
    findings: list[Finding] = []
    for path in files:
        o, f = scan_prompt_file(path, root)
        observations.extend(o)
        findings.extend(f)
    return observations, findings
