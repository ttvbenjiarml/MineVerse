from __future__ import annotations

import json
from pathlib import Path


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
