from __future__ import annotations

from pathlib import Path


def resolve_workspace_path(workspace: Path, candidate: Path) -> Path:
    workspace = workspace.resolve()
    resolved = candidate.resolve()
    if workspace not in [resolved, *resolved.parents]:
        raise PermissionError("Path escapes workspace")
    return resolved


def block_symlink_escape(workspace: Path, candidate: Path) -> Path:
    if candidate.is_symlink() and workspace.resolve() not in [candidate.resolve(), *candidate.resolve().parents]:
        raise PermissionError("Symlink escapes workspace")
    return resolve_workspace_path(workspace, candidate)
