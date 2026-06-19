from __future__ import annotations

from pathlib import Path


ALLOWED_EXTENSIONS = {
    ".java", ".kt", ".kts", ".gradle", ".properties", ".yml", ".yaml", ".json", ".toml", ".md", ".txt", ".xml", ".log", ".mcfunction", ".mcmeta", ".snbt"
}


def allowed_file(path: Path) -> bool:
    return path.suffix in ALLOWED_EXTENSIONS
