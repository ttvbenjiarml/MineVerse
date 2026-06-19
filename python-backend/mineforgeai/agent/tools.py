from __future__ import annotations

from pathlib import Path


def available_tools(permission_mode: str) -> list[str]:
    tools = ["read", "search", "diff"]
    if permission_mode in {"ask_before_actions", "full_access"}:
        tools.append("patch")
    if permission_mode == "full_access":
        tools.append("shell")
    return tools


def describe_workspace(workspace: Path) -> str:
    files = sorted(path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file() and ".mineforgeai" not in path.parts)
    if not files:
        return "The workspace is currently empty. I can generate a new project here from your prompt."
    preview = files[:20]
    more = len(files) - len(preview)
    lines = ["Workspace files:"]
    lines.extend(f"- {item}" for item in preview)
    if more > 0:
        lines.append(f"- ... and {more} more files")
    return "\n".join(lines)


def inspect_logs(workspace: Path) -> str:
    candidates = []
    for pattern in ["latest.log", "debug.log", "*.log", "crash-*.txt"]:
        candidates.extend(workspace.rglob(pattern))
    candidates = [path for path in candidates if path.is_file() and ".mineforgeai" not in path.parts]
    if not candidates:
        return ""
    latest = sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[0]
    snippet = latest.read_text(encoding="utf-8", errors="replace")[:2000]
    return f"Latest likely log: `{latest.relative_to(workspace).as_posix()}`\n\n{snippet}"


def search_workspace_text(workspace: Path, query: str) -> str:
    matches = []
    lowered = query.lower()
    for path in workspace.rglob("*"):
        if not path.is_file() or ".mineforgeai" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if lowered in text.lower():
            matches.append(path.relative_to(workspace).as_posix())
    if not matches:
        return f"I did not find `{query}` in the current workspace."
    return "\n".join([f"Search results for `{query}`:", *[f"- {item}" for item in matches[:20]]])
