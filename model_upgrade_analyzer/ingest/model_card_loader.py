"""Load model cards / lifecycle metadata from markdown and YAML files."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models.domain import ModelCard
from ..utils.dates import parse_date
from ..utils.files import iter_files, read_text
from ..utils.text import normalize_key


FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


_KEY_ALIASES: dict[str, str] = {
    "model": "model_name",
    "name": "model_name",
    "model_name": "model_name",
    "replacement": "replacement",
    "recommended_replacement": "replacement",
    "successor": "replacement",
    "retirement_date": "retirement_date",
    "retire_by": "retirement_date",
    "deprecation_date": "retirement_date",
    "eol": "retirement_date",
    "context_window": "context_window",
    "context_length": "context_window",
    "max_context": "context_window",
    "modalities": "modalities",
    "modality": "modalities",
    "supports_structured_output": "supports_structured_output",
    "structured_output": "supports_structured_output",
    "json_mode": "supports_structured_output",
    "supports_reasoning": "supports_reasoning",
    "reasoning": "supports_reasoning",
    "migration_notes": "migration_notes",
    "notes": "migration_notes",
    "migration": "migration_notes",
}


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("true", "yes", "y", "1", "supported", "supports"):
        return True
    if s in ("false", "no", "n", "0", "unsupported"):
        return False
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in str(value).split(",") if p.strip()]


def _normalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        canonical = _KEY_ALIASES.get(normalize_key(str(k)))
        if canonical:
            out[canonical] = v
    return out


def _parse_markdown(text: str, path: Path) -> ModelCard | None:
    data: dict[str, Any] = {}
    match = FRONT_MATTER_RE.match(text)
    if match:
        try:
            import yaml

            parsed = yaml.safe_load(match.group(1)) or {}
            if isinstance(parsed, dict):
                data.update(parsed)
        except (ImportError, ValueError):
            pass
        except Exception:  # noqa: BLE001 - YAML parser variants raise various errors
            pass

    # Also harvest "Key: value" lines from markdown body for robustness.
    body = text[match.end():] if match else text
    for line in body.splitlines():
        m = re.match(r"[-*]?\s*\*?\*?([A-Za-z][A-Za-z _-]+)\*?\*?\s*[:|]\s*(.+)", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if normalize_key(key) in _KEY_ALIASES and normalize_key(key) not in {normalize_key(k) for k in data}:
                data[key] = value

    norm = _normalize_dict(data)
    if not norm.get("model_name"):
        # Fall back to filename stem
        norm["model_name"] = path.stem

    return ModelCard(
        model_name=str(norm["model_name"]).strip(),
        replacement=(str(norm["replacement"]).strip() if norm.get("replacement") else None),
        retirement_date=parse_date(norm.get("retirement_date")),
        context_window=_coerce_int(norm.get("context_window")),
        modalities=_coerce_list(norm.get("modalities")),
        supports_structured_output=_coerce_bool(norm.get("supports_structured_output")),
        supports_reasoning=_coerce_bool(norm.get("supports_reasoning")),
        migration_notes=(str(norm["migration_notes"]).strip() if norm.get("migration_notes") else None),
        source_path=str(path),
        raw=data,
    )


def _parse_yaml(text: str, path: Path) -> list[ModelCard]:
    import yaml

    data = yaml.safe_load(text)
    entries: list[dict[str, Any]] = []
    if isinstance(data, list):
        entries = [d for d in data if isinstance(d, dict)]
    elif isinstance(data, dict):
        if isinstance(data.get("models"), list):
            entries = [d for d in data["models"] if isinstance(d, dict)]
        else:
            entries = [data]

    cards: list[ModelCard] = []
    for entry in entries:
        norm = _normalize_dict(entry)
        if not norm.get("model_name"):
            continue
        cards.append(
            ModelCard(
                model_name=str(norm["model_name"]).strip(),
                replacement=(str(norm["replacement"]).strip() if norm.get("replacement") else None),
                retirement_date=parse_date(norm.get("retirement_date")),
                context_window=_coerce_int(norm.get("context_window")),
                modalities=_coerce_list(norm.get("modalities")),
                supports_structured_output=_coerce_bool(norm.get("supports_structured_output")),
                supports_reasoning=_coerce_bool(norm.get("supports_reasoning")),
                migration_notes=(str(norm["migration_notes"]).strip() if norm.get("migration_notes") else None),
                source_path=str(path),
                raw=entry,
            )
        )
    return cards


def load_model_cards(root: Path) -> list[ModelCard]:
    """Load all model cards found under the given directory (or single file)."""
    cards: list[ModelCard] = []
    if root.is_file():
        paths = [root]
    else:
        paths = list(iter_files(root, extensions={".md", ".yaml", ".yml"}))
    for path in paths:
        text = read_text(path)
        if not text:
            continue
        if path.suffix.lower() == ".md":
            card = _parse_markdown(text, path)
            if card is not None:
                cards.append(card)
        elif path.suffix.lower() in (".yaml", ".yml"):
            cards.extend(_parse_yaml(text, path))
    return cards
