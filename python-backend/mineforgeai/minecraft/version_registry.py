from __future__ import annotations

import json
from pathlib import Path


class VersionRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.manifest_path = root / "manifest_v2.json"

    def load_manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def version_ids(self) -> list[str]:
        return [entry["id"] for entry in self.load_manifest().get("versions", [])]

    def materialize_version_dirs(self) -> list[Path]:
        manifest = self.load_manifest()
        output = []
        for entry in manifest.get("versions", []):
            version_dir = self.root / "versions" / entry["id"]
            version_dir.mkdir(parents=True, exist_ok=True)
            (version_dir / "version.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
            (version_dir / "metadata.yaml").write_text(
                f"id: {entry['id']}\ntype: {entry.get('type', 'unknown')}\nrelease_time: {entry.get('releaseTime', '')}\n",
                encoding="utf-8",
            )
            (version_dir / "support_matrix.yaml").write_text(
                "paper: best_effort\nfabric: best_effort\nforge: best_effort\nneoforge: best_effort\n",
                encoding="utf-8",
            )
            output.append(version_dir)
        return output
