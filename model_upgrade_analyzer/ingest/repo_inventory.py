"""Build a lightweight inventory of files in the target repo."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import AnalyzerConfig
from ..utils.files import iter_files, is_probably_prompt_path


@dataclass
class RepoInventory:
    root: Path
    code_files: list[Path] = field(default_factory=list)
    prompt_files: list[Path] = field(default_factory=list)
    config_files: list[Path] = field(default_factory=list)
    notebook_files: list[Path] = field(default_factory=list)


_CONFIG_EXT = {".json", ".yaml", ".yml", ".env", ".toml", ".ini", ".bicep", ".tf"}
_PROMPT_EXT = {".md", ".txt", ".prompt", ".jinja", ".j2", ".tmpl", ".tpl"}


def build_inventory(config: AnalyzerConfig) -> RepoInventory:
    inv = RepoInventory(root=config.repo_path)
    for path in iter_files(
        config.repo_path,
        ignore_dirs=config.ignore_dirs,
        extensions=set(config.code_extensions) | _PROMPT_EXT,
        max_bytes=config.max_file_bytes,
    ):
        ext = path.suffix.lower()
        if ext == ".ipynb":
            inv.notebook_files.append(path)
            continue
        if is_probably_prompt_path(path, config.prompt_dir_names) or ext in _PROMPT_EXT:
            inv.prompt_files.append(path)
        if ext in _CONFIG_EXT:
            inv.config_files.append(path)
        if ext in {".py", ".js", ".ts", ".tsx", ".jsx"}:
            inv.code_files.append(path)
        elif ext == ".md" and not is_probably_prompt_path(path, config.prompt_dir_names):
            # markdown that isn't in a prompt dir — still scanned as docs
            inv.code_files.append(path)
    return inv
