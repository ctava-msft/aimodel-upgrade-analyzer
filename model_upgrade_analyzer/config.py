"""Runtime configuration for the analyzer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# File extensions handled by the code scanner.
CODE_EXTENSIONS: tuple[str, ...] = (
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".yaml", ".yml",
    ".env", ".toml", ".ini",
    ".md", ".ipynb",
    ".bicep", ".tf",
)

# Directories that typically hold prompt content.
PROMPT_DIR_NAMES: tuple[str, ...] = (
    "prompts", "system-prompts", "system_prompts",
    "templates", "instructions", "chains",
)

# Files/paths to skip during scanning.
DEFAULT_IGNORES: tuple[str, ...] = (
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", ".next", ".cache", ".mypy_cache", ".pytest_cache",
)


@dataclass
class AnalyzerConfig:
    """Top-level configuration for a single analyzer run."""

    repo_path: Path
    modeliq_path: Path | None = None
    model_cards_path: Path | None = None
    output_dir: Path = Path("reports")
    formats: tuple[str, ...] = ("json", "md")
    ignore_dirs: tuple[str, ...] = DEFAULT_IGNORES
    code_extensions: tuple[str, ...] = CODE_EXTENSIONS
    prompt_dir_names: tuple[str, ...] = PROMPT_DIR_NAMES
    max_file_bytes: int = 2 * 1024 * 1024  # skip large files

    def should_ignore_dir(self, name: str) -> bool:
        return name in self.ignore_dirs

    def iter_formats(self) -> Iterable[str]:
        return self.formats
