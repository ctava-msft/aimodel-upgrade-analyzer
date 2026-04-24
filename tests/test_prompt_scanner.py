"""Tests for the prompt scanner."""
from __future__ import annotations

from pathlib import Path

from model_upgrade_analyzer.scanners.prompt_scanner import scan_prompt_file


def test_strict_json_and_cot(tmp_path: Path) -> None:
    p = tmp_path / "prompts" / "system.md"
    p.parent.mkdir(parents=True)
    p.write_text(
        "You are a helpful assistant.\n"
        "Let's think step by step.\n"
        "Respond only in JSON following the schema below.\n"
        "Example 1: {}\nExample 2: {}\n"
    )
    obs, findings = scan_prompt_file(p, tmp_path)
    traits = {o.trait for o in obs}
    assert "strict_json" in traits
    assert "chain_of_thought" in traits
    finding_types = {f.finding_type for f in findings}
    assert "strict_json_output_expectation" in finding_types
    assert "chain_of_thought_prompt" in finding_types
    assert "brittle_few_shot" in finding_types


def test_deprecated_model_in_prompt(tmp_path: Path) -> None:
    p = tmp_path / "prompts" / "legacy.md"
    p.parent.mkdir(parents=True)
    p.write_text("You are running on text-davinci-003 and must behave accordingly.\n")
    _obs, findings = scan_prompt_file(p, tmp_path)
    assert any(f.finding_type == "deprecated_model_in_prompt" for f in findings)


def test_token_heavy(tmp_path: Path) -> None:
    p = tmp_path / "prompts" / "big.md"
    p.parent.mkdir(parents=True)
    p.write_text("word " * 2000)  # ~10k chars → ~2500 tokens
    _obs, findings = scan_prompt_file(p, tmp_path)
    assert any(f.finding_type == "token_heavy_prompt" for f in findings)
