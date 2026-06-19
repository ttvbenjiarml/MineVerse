from __future__ import annotations


def _extract_preferences(messages: list[dict]) -> list[str]:
    preferences = []
    for message in messages:
        if message.get("role") != "user":
            continue
        text = message.get("content", "")
        lowered = text.lower()
        if "prefer" in lowered or "use java" in lowered or "use kotlin" in lowered or "call me" in lowered:
            preferences.append(text[:160])
    return preferences[:8]


def _extract_goals(messages: list[dict]) -> list[str]:
    goals = []
    for message in messages:
        if message.get("role") != "user":
            continue
        text = message.get("content", "")
        lowered = text.lower()
        if any(keyword in lowered for keyword in ["make ", "build ", "fix ", "create ", "train ", "plugin", "mod", "datapack", "resource pack"]):
            goals.append(text[:160])
    return goals[:10]


def summarize_messages(messages: list[dict]) -> str:
    goals = _extract_goals(messages)
    preferences = _extract_preferences(messages)
    notes = [message.get("content", "")[:120] for message in messages if message.get("content")][:12]
    if not goals and not preferences and not notes:
        return "No prior conversation."
    return "\n".join([
        "# Conversation Summary",
        "",
        "## User Goals",
        *([f"- {item}" for item in goals] or ["- none captured"]),
        "",
        "## User Preferences",
        *([f"- {item}" for item in preferences] or ["- none captured"]),
        "",
        "## Long-Term Memory Intent",
        "- Keep plugin/mod/datapack/resource-pack requirements stable across future turns.",
        "- Preserve version targets, Java compatibility, permissions, web mode, and major design decisions.",
        "",
        "## Preserved Notes",
        *[f"- {item}" for item in notes],
    ])
