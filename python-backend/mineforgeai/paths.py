from __future__ import annotations

import os
import platform
from pathlib import Path


def user_data_dir() -> Path:
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "MineForgeAI"
    if system == "Darwin":
        return home / "Library" / "Application Support" / "MineForgeAI"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "mineforgeai"


def cache_dir() -> Path:
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "MineForgeAI" / "cache"
    if system == "Darwin":
        return home / "Library" / "Caches" / "MineForgeAI"
    return Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "mineforgeai"


def workspace_state_dir(workspace: Path) -> Path:
    return workspace / ".mineforgeai"


def user_models_dir() -> Path:
    return user_data_dir() / "models"


def latest_model_dir() -> Path:
    return user_models_dir() / "latest"
