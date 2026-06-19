from __future__ import annotations

import json
from pathlib import Path


def bootstrap_workspace(workspace: Path) -> dict:
    state = workspace / ".mineforgeai"
    for child in [
        state,
        state / "conversations",
        state / "index",
        state / "logs",
        state / "patches",
        state / "web_cache",
    ]:
        child.mkdir(parents=True, exist_ok=True)
    directives = state / "directives.md"
    if not directives.exists():
        directives.write_text(
            "You are MineForgeAI, a local Minecraft development chatbot and coding agent.\n",
            encoding="utf-8",
        )
    permissions = state / "permissions.json"
    if not permissions.exists():
        permissions.write_text(json.dumps({"mode": "ask_before_actions"}, indent=2), encoding="utf-8")
    memory = state / "memory.json"
    if not memory.exists():
        memory.write_text(json.dumps({"web_enabled": False}, indent=2), encoding="utf-8")
    return {"workspace": str(workspace), "state_dir": str(state)}
