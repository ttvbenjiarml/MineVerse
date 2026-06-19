from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "minecraft_versions"
    manifest = json.loads((root / "manifest_v2.json").read_text(encoding="utf-8"))
    versions_root = root / "versions"
    versions_root.mkdir(parents=True, exist_ok=True)
    for entry in manifest.get("versions", []):
        version_dir = versions_root / entry["id"]
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "version.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
        (version_dir / "metadata.yaml").write_text(
            "\n".join(
                [
                    f"id: {entry['id']}",
                    f"type: {entry.get('type', 'unknown')}",
                    f"release_time: {entry.get('releaseTime', '')}",
                    f"update_time: {entry.get('time', '')}",
                    "java_requirement: unknown",
                    "official_mappings: best_effort",
                    "yarn: best_effort",
                    "intermediary: best_effort",
                    "mcp_srg: best_effort",
                    "parchment: best_effort",
                    "datapack_format: unknown",
                    "resource_pack_format: unknown",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (version_dir / "support_matrix.yaml").write_text(
            "paper: best_effort\nspigot: best_effort\nbukkit: best_effort\npurpur: best_effort\nfabric: best_effort\nquilt: best_effort\nforge: best_effort\nneoforge: best_effort\nsponge: best_effort\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
