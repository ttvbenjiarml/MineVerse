from __future__ import annotations

from pathlib import Path

from mineforgeai.paths import latest_model_dir


def checkpoint_paths(base_dir: Path) -> dict:
    return {
        "model": base_dir / "model.pt",
        "optimizer": base_dir / "optimizer.pt",
        "state": base_dir / "state.json",
    }


def model_artifact_paths(base_dir: Path) -> dict:
    return {
        "weights": base_dir / "model.pt",
        "state": base_dir / "state.json",
        "tokenizer": base_dir / "tokenizer.json",
        "config": base_dir / "model_config.json",
    }


def required_model_artifact_paths(base_dir: Path) -> dict:
    artifacts = model_artifact_paths(base_dir)
    return {name: artifacts[name] for name in ["weights", "tokenizer", "config"]}


def trained_model_locations(workspace: Path) -> list[Path]:
    return [
        workspace / ".mineforgeai" / "models" / "latest",
        latest_model_dir(),
        Path("models") / "latest",
    ]


def find_trained_model_dir(workspace: Path) -> Path | None:
    for candidate in trained_model_locations(workspace):
        artifacts = required_model_artifact_paths(candidate)
        if all(path.exists() for path in artifacts.values()):
            return candidate
    return None


def has_trained_model(workspace: Path) -> bool:
    return find_trained_model_dir(workspace) is not None
