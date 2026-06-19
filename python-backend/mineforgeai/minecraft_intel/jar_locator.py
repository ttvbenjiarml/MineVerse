from __future__ import annotations

from pathlib import Path


def known_minecraft_dirs(home: Path) -> list[Path]:
    return [
        home / ".minecraft",
        home / "AppData" / "Roaming" / ".minecraft",
        home / "Library" / "Application Support" / "minecraft",
        home / "PrismLauncher",
        home / "MultiMC",
        home / "ModrinthApp",
        home / "curseforge" / "minecraft",
    ]
