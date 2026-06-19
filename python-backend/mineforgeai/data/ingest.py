from __future__ import annotations

from pathlib import Path

from mineforgeai.data.datasets import allowed_file


def ingest_paths(base: Path) -> list[Path]:
    return [path for path in base.rglob("*") if path.is_file() and allowed_file(path)]
