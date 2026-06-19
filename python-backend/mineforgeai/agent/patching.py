from __future__ import annotations

import json
from pathlib import Path


def write_patch_history(workspace: Path, patch_text: str, sequence: int) -> Path:
    patches = workspace / ".mineforgeai" / "patches"
    patches.mkdir(parents=True, exist_ok=True)
    patch_file = patches / f"patch-{sequence:03d}.diff"
    meta_file = patches / f"patch-{sequence:03d}-meta.json"
    patch_file.write_text(patch_text, encoding="utf-8")
    meta_file.write_text(json.dumps({"sequence": sequence, "bytes": len(patch_text)}), encoding="utf-8")
    return patch_file
