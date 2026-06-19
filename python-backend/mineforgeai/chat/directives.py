from __future__ import annotations

from pathlib import Path


def load_directives(workspace: Path) -> str:
    file = workspace / ".mineforgeai" / "directives.md"
    if file.exists():
        return file.read_text(encoding="utf-8")
    return ""
