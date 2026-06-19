from __future__ import annotations

from pathlib import Path


def index_zip(path: Path) -> dict:
    return {"path": str(path), "indexed": path.suffix == ".zip"}
