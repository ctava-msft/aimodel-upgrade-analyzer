"""File traversal and safe reading utilities."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator


def iter_files(
    root: Path,
    ignore_dirs: Iterable[str] = (),
    extensions: Iterable[str] | None = None,
    max_bytes: int | None = None,
) -> Iterator[Path]:
    """Yield files under root, skipping ignored dirs and oversized files."""
    ignore = set(ignore_dirs)
    exts: set[str] | None = {e.lower() for e in extensions} if extensions else None
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in ignore and not d.startswith(".git")]
        for name in filenames:
            p = Path(dirpath) / name
            if exts is not None and p.suffix.lower() not in exts:
                continue
            if max_bytes is not None:
                try:
                    if p.stat().st_size > max_bytes:
                        continue
                except OSError:
                    continue
            yield p


def read_text(path: Path, encoding: str = "utf-8") -> str:
    """Read text; return empty string on failure instead of raising."""
    try:
        return path.read_text(encoding=encoding, errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def is_probably_prompt_path(path: Path, prompt_dir_names: Iterable[str]) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(name.lower() in parts for name in prompt_dir_names)
