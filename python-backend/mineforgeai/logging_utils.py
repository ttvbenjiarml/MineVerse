from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path


def jsonl_log(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": datetime.now(UTC).isoformat(), **payload}) + "\n")
