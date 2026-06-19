from __future__ import annotations

import re

from mineforgeai.chat.clarification import clarification_question


def route_message(text: str) -> dict:
    normalized = text.lower().strip()
    if normalized.startswith("/"):
        allowed = {"/permisions", "/permissions", "/web on", "/web off"}
        if normalized not in allowed:
            return {"type": "invalid_slash", "message": "Only /permisions and /web on/off are available. Just tell me what you want in normal chat."}

    if "custom sword plugin" in normalized and "paper" not in normalized and "fabric" not in normalized and "forge" not in normalized:
        return {
            "type": "clarification",
            "message": clarification_question(
                "What Minecraft platform should I target?",
                ["Paper plugin", "Fabric mod", "Forge/NeoForge mod"],
            ),
        }

    version_match = re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", normalized)
    version = version_match.group(1) if version_match else None
    hours_match = re.search(r"for\s+(\d+(?:\.\d+)?)\s+hours?", normalized)
    hours = float(hours_match.group(1)) if hours_match else 2

    if normalized.startswith("read this project") or normalized.startswith("fix this project"):
        return {"type": "workspace_review"}
    if normalized.startswith("find ") or normalized.startswith("search this project for "):
        query = normalized.split("for ", 1)[-1] if " for " in normalized else normalized.replace("find ", "", 1)
        return {"type": "search_workspace", "query": query.strip()}
    if "paper" in normalized and "plugin" in normalized:
        sword = "sword" in normalized
        return {
            "type": "generate_project",
            "platform": "paper",
            "language": "java",
            "build": "gradle_kotlin",
            "version": version or "1.21.1",
            "version_explicit": version is not None,
            "feature": "custom_sword_vfx" if sword else "paper_plugin",
            "project_name": "CustomSwordVFX" if sword else "PaperPlugin",
            "suggested_name": "CustomSwordVFX" if sword else "PaperPlugin",
            "package_name": "com.mineforgeai.customsword",
        }
    if "fabric" in normalized and "mod" in normalized:
        ore = "ore" in normalized or "armor" in normalized
        return {
            "type": "generate_project",
            "platform": "fabric",
            "language": "java",
            "build": "gradle_kotlin",
            "version": version or "1.20.1",
            "version_explicit": version is not None,
            "feature": "ore_armor" if ore else "fabric_mod",
            "project_name": "CopperArmorSet" if ore else "FabricMod",
            "suggested_name": "CopperArmorSet" if ore else "FabricMod",
            "package_name": "com.mineforgeai.fabricmod",
        }
    if "train the local model" in normalized:
        return {"type": "train_model", "hours": hours}
    if "crash" in normalized or "latest.log" in normalized:
        return {"type": "analyze_crash"}
    return {"type": "chat"}
