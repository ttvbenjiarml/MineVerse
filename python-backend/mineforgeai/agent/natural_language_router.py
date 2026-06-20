from __future__ import annotations

import re

from mineforgeai.chat.clarification import clarification_question


def _project_name_from_text(text: str, fallback: str) -> str:
    quoted = re.search(r"\b(?:called|named)\s+[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    bare = re.search(r"\b(?:called|named)\s+([A-Za-z][A-Za-z0-9_-]*)", text, re.IGNORECASE)
    raw = (quoted.group(1) if quoted else bare.group(1) if bare else fallback).strip()
    parts = re.findall(r"[A-Za-z0-9]+", raw)
    if not parts:
        return fallback
    candidate = "".join(part[:1].upper() + part[1:] for part in parts)
    if not candidate[0].isalpha():
        candidate = fallback
    return candidate


def _package_name_for(project_name: str, suffix: str) -> str:
    safe_name = re.sub(r"[^a-z0-9]", "", project_name.lower())
    return f"com.mineforgeai.{safe_name or suffix}"


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
        project_name = _project_name_from_text(text, "CustomSwordVFX" if sword else "PaperPlugin")
        return {
            "type": "generate_project",
            "platform": "paper",
            "language": "java",
            "build": "gradle_kotlin",
            "version": version or "1.21.1",
            "version_explicit": version is not None,
            "feature": "custom_sword_vfx" if sword else "paper_plugin",
            "project_name": project_name,
            "suggested_name": project_name,
            "package_name": _package_name_for(project_name, "paperplugin"),
        }
    if "fabric" in normalized and "mod" in normalized:
        ore = "ore" in normalized or "armor" in normalized
        project_name = _project_name_from_text(text, "CopperArmorSet" if ore else "FabricMod")
        return {
            "type": "generate_project",
            "platform": "fabric",
            "language": "java",
            "build": "gradle_kotlin",
            "version": version or "1.20.1",
            "version_explicit": version is not None,
            "feature": "ore_armor" if ore else "fabric_mod",
            "project_name": project_name,
            "suggested_name": project_name,
            "package_name": _package_name_for(project_name, "fabricmod"),
        }
    if "train the local model" in normalized:
        return {"type": "train_model", "hours": hours}
    if "crash" in normalized or "latest.log" in normalized:
        return {"type": "analyze_crash"}
    return {"type": "chat"}
