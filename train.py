"""
train.py - small launcher for the training plan

This script uses the existing python-backend trainer to write a training
plan and optionally kick off any training pipeline that might be present.
It is lightweight on purpose: the heavy training machinery lives inside
the python-backend package.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
# ensure workspace root and python-backend are importable
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python-backend"))

from mineforgeai.training.trainer import write_training_plan, run_training
import config
from mineforgeai.paths import latest_model_dir


def ensure_workspace() -> Path:
    return Path.cwd()


def main(hours: float | None = None, workspace: Path | None = None) -> int:
    workspace = workspace or ensure_workspace()
    use_hours = hours if hours is not None else config.training_hours
    plan = write_training_plan(use_hours, workspace)
    print(f"Wrote training plan to: {plan}")
    print("Starting training loop...")
    # If a PAUSED flag exists from a previous run, remove it so the trainer will resume
    try:
        latest = latest_model_dir()
        paused = latest / "PAUSED"
        if paused.exists():
            paused.unlink()
            print("Cleared PAUSED flag; resuming from last checkpoint.")
    except Exception:
        pass
    try:
        model_dir = run_training(use_hours, workspace)
        print(f"Training finished. Artifacts saved to: {model_dir}")
    except Exception as exc:
        print(f"Training failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Launch training plan and run training loop")
    parser.add_argument("--hours", type=float, help="Override training hours from config")
    parser.add_argument("--workspace", type=str, help="Workspace path to use")
    args = parser.parse_args()
    # Auto-install missing deps and relaunch under created venv to pick them up.
    def _ensure_deps_and_relaunch_if_needed():
        # If we were relaunched into the venv, still ensure missing packages
        relaunched = os.environ.get("MINEFORGE_AUTO_RELAUNCHED") == "1"
        missing = []
        try:
            import torch  # type: ignore
        except Exception:
            missing.append("torch")
        try:
            import numpy  # type: ignore
        except Exception:
            missing.append("numpy")

        if not missing:
            return

        print(f"Missing packages: {missing}. Creating virtualenv and installing Python requirements...")
        try:
            import start_bot  # type: ignore
        except Exception as exc:
            print(f"Failed to import start_bot installer: {exc}")
            return

        try:
            start_bot.create_venv()
            start_bot.pip_install_requirements()
        except Exception as exc:
            print(f"Python dependency installation failed: {exc}")
        try:
            start_bot.npm_install()
        except Exception as exc:
            print(f"npm install failed: {exc}")

        # If we haven't already relaunched into the venv, try to relaunch now
        if not relaunched:
            try:
                vpython = str(start_bot._venv_python())
                if not Path(vpython).exists():
                    print(f"Virtualenv python not found at {vpython}; skipping relaunch")
                else:
                    new_env = os.environ.copy()
                    new_env["MINEFORGE_AUTO_RELAUNCHED"] = "1"
                    args_list = [vpython, "-u", str(Path(__file__).resolve())] + sys.argv[1:]
                    print(f"Relaunching with venv python: {vpython}")
                    # Use subprocess to spawn the venv python and exit this process
                    result = subprocess.run(args_list, env=new_env)
                    sys.exit(result.returncode)
            except Exception as exc:
                print(f"Failed to relaunch under venv python: {exc}")

        # If we are already relaunched (or relaunch failed) and packages are still missing,
        # attempt to install them in-place using the current python executable.
        try:
            vpython = sys.executable
            for pkg in missing:
                print(f"Installing missing package in-place: {pkg}")
                subprocess.check_call([vpython, "-m", "pip", "install", pkg])
        except Exception as exc:
            print(f"In-place pip install failed: {exc}")

    # Ensure dependencies are present before either GUI or headless mode.
    _ensure_deps_and_relaunch_if_needed()

    # If no flags provided, open the GUI. Otherwise run headless training.
    if args.hours is None and args.workspace is None:
        try:
            # train_gui lives under python-backend (sys.path was updated above)
            import train_gui  # type: ignore
            train_gui.main()
            raise SystemExit(0)
        except Exception as exc:
            print(f"Failed to launch GUI: {exc}")
            # fall through to headless mode

    ws = Path(args.workspace) if args.workspace else None
    raise SystemExit(main(args.hours, ws))
