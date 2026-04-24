"""Detect Azure OpenAI deployment type (PTU vs. standard) from text signals.

Used by the Model IQ loader (to classify records from SKU/offering fields) and by
the code/config scanners (to flag deployment-type usage in Bicep/ARM/YAML/JSON).

Canonical Azure OpenAI SKU / offering names include:
  - Standard                  (token-billed, regional)
  - GlobalStandard            (token-billed, global)
  - DataZoneStandard          (token-billed, data-zone)
  - ProvisionedManaged        (PTU, regional)
  - GlobalProvisionedManaged  (PTU, global)
  - DataZoneProvisionedManaged (PTU, data-zone)
  - Batch / GlobalBatch       (batch)
"""
from __future__ import annotations

import re

from ..models.domain import DeploymentType


# Regex patterns keyed by deployment type. Case-insensitive.
# NB: camel-case names like "GlobalProvisionedManaged" do not contain word boundaries
# between the parts, so we deliberately do NOT require \b at the start of the PTU words.
_PATTERNS: dict[DeploymentType, list[re.Pattern[str]]] = {
    DeploymentType.PTU: [
        re.compile(r"provisioned[\s_-]*managed", re.IGNORECASE),
        re.compile(r"global[\s_-]*provisioned", re.IGNORECASE),
        re.compile(r"data[\s_-]*zone[\s_-]*provisioned", re.IGNORECASE),
        re.compile(r"provisioned", re.IGNORECASE),
        re.compile(r"\bPTU(?:-?M)?\b"),
        re.compile(r"\bPTUs?\b"),
    ],
    DeploymentType.BATCH: [
        re.compile(r"global[\s_-]*batch", re.IGNORECASE),
        re.compile(r"\bbatch\b", re.IGNORECASE),
    ],
    DeploymentType.STANDARD: [
        re.compile(r"global[\s_-]*standard", re.IGNORECASE),
        re.compile(r"data[\s_-]*zone[\s_-]*standard", re.IGNORECASE),
        re.compile(r"pay[\s_-]*as[\s_-]*you[\s_-]*go", re.IGNORECASE),
        re.compile(r"\bPAYG\b"),
        re.compile(r"\bstandard\b", re.IGNORECASE),
        re.compile(r"token[\s_-]*billed", re.IGNORECASE),
    ],
}


# Known literal SKU tokens that unambiguously identify a deployment type when found
# anywhere in an IaC file or config value. Ordered: PTU first so "Standard" inside
# "ProvisionedManaged" (doesn't exist, but sibling keys might) doesn't win.
_LITERAL_SKU_TOKENS: list[tuple[re.Pattern[str], DeploymentType]] = [
    (re.compile(r"\b(GlobalProvisionedManaged)\b"), DeploymentType.PTU),
    (re.compile(r"\b(DataZoneProvisionedManaged)\b"), DeploymentType.PTU),
    (re.compile(r"\b(ProvisionedManaged)\b"), DeploymentType.PTU),
    (re.compile(r"\b(GlobalBatch)\b"), DeploymentType.BATCH),
    (re.compile(r"\b(GlobalStandard)\b"), DeploymentType.STANDARD),
    (re.compile(r"\b(DataZoneStandard)\b"), DeploymentType.STANDARD),
]


# Bicep/ARM/YAML key names that typically carry a deployment SKU value.
SKU_KEY_PATTERN = re.compile(
    r"""(?P<key>sku[_\s-]?name|skuName|sku|offering|deployment[_\s-]?type|tier|capacity[_\s-]?type)\s*[:=]\s*["']?([A-Za-z][A-Za-z0-9_\s-]{2,60})["']?""",
    re.IGNORECASE,
)


CAPACITY_KEY_PATTERN = re.compile(
    r"""(?P<key>capacity|provisioned[_\s-]?capacity|ptu[_\s-]?count|sku[_\s-]?capacity)\s*[:=]\s*["']?(\d{1,6})["']?""",
    re.IGNORECASE,
)


def classify_text(value: str | None) -> DeploymentType:
    """Classify a free-form SKU/offering string into a DeploymentType."""
    if not value:
        return DeploymentType.UNKNOWN
    # PTU is checked first because "ProvisionedManaged" contains "Managed" and we want
    # to avoid a Standard false positive from substrings.
    for dtype in (DeploymentType.PTU, DeploymentType.BATCH, DeploymentType.STANDARD):
        for pat in _PATTERNS[dtype]:
            if pat.search(value):
                return dtype
    return DeploymentType.UNKNOWN


def scan_text_for_deployment_types(text: str) -> list[tuple[DeploymentType, re.Match[str]]]:
    """Return (type, match) tuples for SKU values found in a text blob.

    Two passes:
      1. Key-anchored: `sku: "ProvisionedManaged"`, `skuName = 'GlobalStandard'`, etc.
      2. Literal-token: unambiguous SKU names found anywhere (e.g. nested under
         `sku: { name: 'ProvisionedManaged' }` in Bicep).

    PTU wins over Standard when both are seen at the same location.
    """
    hits: list[tuple[DeploymentType, re.Match[str]]] = []
    seen_spans: set[tuple[int, int]] = set()

    for m in SKU_KEY_PATTERN.finditer(text):
        value = m.group(2)
        dtype = classify_text(value)
        if dtype != DeploymentType.UNKNOWN:
            hits.append((dtype, m))
            seen_spans.add(m.span())

    for pat, dtype in _LITERAL_SKU_TOKENS:
        for m in pat.finditer(text):
            if m.span() in seen_spans:
                continue
            hits.append((dtype, m))
            seen_spans.add(m.span())
    return hits


def extract_capacity(text: str) -> int | None:
    """Return the first integer capacity/ptu_count value found in text, if any."""
    m = CAPACITY_KEY_PATTERN.search(text)
    if not m:
        return None
    try:
        return int(m.group(2))
    except (TypeError, ValueError):
        return None
