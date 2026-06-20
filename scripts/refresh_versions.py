from __future__ import annotations

import json
import urllib.request
import argparse
from pathlib import Path


MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not download a fresh Mojang manifest; only materialize folders from the local manifest.",
    )
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Write minecraft_versions/versions/<id>/ metadata folders. By default the compact manifest is updated only.",
    )
    return parser


def download_manifest() -> dict:
    with urllib.request.urlopen(MANIFEST_URL, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1] / "minecraft_versions"
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest_v2.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if args.offline else download_manifest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if not args.materialize:
        print(f"Updated compact manifest with {len(manifest.get('versions', []))} versions.")
        return 0
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
