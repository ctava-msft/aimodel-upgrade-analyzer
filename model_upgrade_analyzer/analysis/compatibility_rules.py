"""Deterministic compatibility rules between current and target models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompatibilityVerdict:
    compatible: bool
    notes: list[str]
    likely_parameter_changes: list[str]


# Families roughly grouped for compatibility reasoning.
_REASONING_FAMILY = {"o1", "o1-preview", "o1-mini", "o1-pro", "o3", "o3-mini", "o3-pro", "o4", "o4-mini"}
_CHAT_FAMILY_PREFIX = ("gpt-3.5", "gpt-4", "gpt-4o", "gpt-4.1", "gpt-5")


def _family(model: str) -> str:
    m = model.lower()
    if m in _REASONING_FAMILY or m.startswith(("o1", "o3", "o4")):
        return "reasoning"
    if m.startswith(_CHAT_FAMILY_PREFIX):
        return "chat"
    if m.startswith("text-embedding"):
        return "embedding"
    if m.startswith("whisper"):
        return "audio"
    if m.startswith("dall-e"):
        return "image"
    return "unknown"


def assess_compatibility(current: str | None, target: str | None) -> CompatibilityVerdict:
    notes: list[str] = []
    param_changes: list[str] = []

    if not current or not target:
        return CompatibilityVerdict(compatible=True, notes=["Missing model information; assume compatible."],
                                    likely_parameter_changes=[])

    cur_fam = _family(current)
    tgt_fam = _family(target)

    if cur_fam != tgt_fam:
        notes.append(f"Family change: {cur_fam} → {tgt_fam}. Expect behavioral differences.")

    # Reasoning models: temperature often not supported; use reasoning_effort.
    if tgt_fam == "reasoning":
        param_changes.extend(["drop temperature/top_p", "add reasoning_effort",
                              "use max_completion_tokens instead of max_tokens"])
        notes.append("Target is a reasoning model: may not accept temperature/top_p; use reasoning_effort.")

    if cur_fam == "reasoning" and tgt_fam == "chat":
        param_changes.extend(["add temperature/top_p as appropriate", "remove reasoning_effort"])
        notes.append("Moving from reasoning to chat family: reinstate sampling parameters.")

    # Embedding dim changes between families
    if cur_fam == "embedding" and tgt_fam == "embedding" and current.lower() != target.lower():
        notes.append("Embedding dimensions may differ; re-embed indexes and verify vector store schema.")
        param_changes.append("re-embed stored vectors")

    compatible = cur_fam == tgt_fam or cur_fam == "unknown" or tgt_fam == "unknown"
    return CompatibilityVerdict(compatible=compatible, notes=notes, likely_parameter_changes=param_changes)
