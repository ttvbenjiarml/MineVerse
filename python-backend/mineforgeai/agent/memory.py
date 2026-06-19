from __future__ import annotations

import json
from pathlib import Path


def _memory_path(workspace: Path) -> Path:
    return workspace / ".mineforgeai" / "memory.json"


def save_memory(workspace: Path, payload: dict) -> None:
    state = workspace / ".mineforgeai"
    state.mkdir(parents=True, exist_ok=True)
    _memory_path(workspace).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_memory(workspace: Path) -> dict:
    path = _memory_path(workspace)
    if not path.exists():
        return {"web_enabled": False}
    return json.loads(path.read_text(encoding="utf-8"))


def append_conversation_message(workspace: Path, conversation_dir: Path, role: str, content: str) -> None:
    conversation_dir.mkdir(parents=True, exist_ok=True)
    payload = {"role": role, "content": content}
    with (conversation_dir / "messages.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def update_memory_insights(workspace: Path, role: str, content: str) -> None:
    payload = load_memory(workspace)
    insights = payload.setdefault("insights", {"goals": [], "preferences": [], "important_facts": []})
    lowered = content.lower()

    if role == "user":
        if any(keyword in lowered for keyword in ["make ", "build ", "create ", "fix ", "train ", "plugin", "mod", "datapack", "resource pack"]):
            goal = content[:200]
            if goal not in insights["goals"]:
                insights["goals"] = (insights["goals"] + [goal])[-20:]
        if any(keyword in lowered for keyword in ["prefer", "always use", "use java", "use kotlin", "remember", "call me"]):
            preference = content[:200]
            if preference not in insights["preferences"]:
                insights["preferences"] = (insights["preferences"] + [preference])[-20:]

    if any(keyword in lowered for keyword in ["paper", "fabric", "forge", "neoforge", "velocity", "spigot", "datapack", "resource pack", "java ", "gradle", "error", "crash"]):
        fact = content[:200]
        if fact not in insights["important_facts"]:
            insights["important_facts"] = (insights["important_facts"] + [fact])[-40:]

    save_memory(workspace, payload)
