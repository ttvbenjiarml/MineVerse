from __future__ import annotations

import json
from pathlib import Path


def _version_tuple(version: str | None) -> tuple[int, int, int]:
    parts = []
    for item in (version or "1.21.1").split("."):
        try:
            parts.append(int(item))
        except ValueError:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _datapack_function_folder(version: str | None) -> str:
    return "function" if _version_tuple(version) >= (1, 21, 0) else "functions"


def validate_plugin_yml(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    issues = []
    for required in ["name:", "main:", "version:"]:
        if required not in text:
            issues.append(f"Missing {required.rstrip(':')} in plugin.yml")
    return issues


def validate_build_gradle_kts(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    issues = []
    if "paper-api" not in text and "fabric-loom" not in text and "net.neoforged" not in text:
        issues.append("Build file does not declare a known Minecraft dependency or plugin")
    return issues


def validate_fabric_mod_json(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues = []
    for key in ["id", "version", "name", "entrypoints"]:
        if key not in payload:
            issues.append(f"Missing {key} in fabric.mod.json")
    return issues


def validate_pack_mcmeta(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues = []
    pack = payload.get("pack")
    if not isinstance(pack, dict):
        return ["Missing pack object in pack.mcmeta"]
    if not isinstance(pack.get("pack_format"), int):
        issues.append("Missing numeric pack_format in pack.mcmeta")
    if not pack.get("description"):
        issues.append("Missing description in pack.mcmeta")
    return issues


def validate_datapack(root: Path, namespace: str, version: str | None = None) -> list[str]:
    issues = validate_pack_mcmeta(root / "pack.mcmeta")
    function_folder = _datapack_function_folder(version)
    tag_folder = "function" if _version_tuple(version) >= (1, 21, 0) else "functions"
    required = [
        root / "data" / "minecraft" / "tags" / tag_folder / "load.json",
        root / "data" / "minecraft" / "tags" / tag_folder / "tick.json",
        root / "data" / namespace / function_folder / "load.mcfunction",
        root / "data" / namespace / function_folder / "tick.mcfunction",
    ]
    for path in required:
        if not path.exists():
            issues.append(f"Missing datapack file: {path.relative_to(root)}")
    for tag_path in required[:2]:
        if tag_path.exists():
            payload = json.loads(tag_path.read_text(encoding="utf-8"))
            if not isinstance(payload.get("values"), list) or not payload["values"]:
                issues.append(f"Tag has no values: {tag_path.relative_to(root)}")
    return issues


def validate_resource_pack(root: Path, namespace: str) -> list[str]:
    issues = validate_pack_mcmeta(root / "pack.mcmeta")
    required = [
        root / "assets" / namespace / "lang" / "en_us.json",
        root / "assets" / namespace / "models" / "item" / "storm_blade.json",
        root / "assets" / namespace / "models" / "item" / "storm_crystal.json",
        root / "assets" / namespace / "textures" / "item" / "storm_blade.png",
        root / "assets" / namespace / "textures" / "item" / "storm_crystal.png",
    ]
    for path in required:
        if not path.exists():
            issues.append(f"Missing resource pack file: {path.relative_to(root)}")
    for png_path in required[-2:]:
        if png_path.exists() and png_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            issues.append(f"Invalid PNG signature: {png_path.relative_to(root)}")
    return issues
