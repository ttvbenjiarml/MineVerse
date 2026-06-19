from __future__ import annotations

import argparse
from pathlib import Path

from mineforgeai.bootstrap import bootstrap_workspace
from mineforgeai.cli.interactive import InteractiveApp, startup_text
from mineforgeai.hardware import detect_hardware
from mineforgeai.model.checkpointing import find_trained_model_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--mode", default="chatbot")
    parser.add_argument("--interactive", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).resolve()
    bootstrap_workspace(workspace)
    profile = detect_hardware()
    model_dir = find_trained_model_dir(workspace)
    has_model = model_dir is not None
    model_label = f"local {profile.device}/{profile.precision} ({model_dir})" if model_dir is not None else f"{profile.preset} [{profile.device}/{profile.precision}]"
    if args.interactive:
        return InteractiveApp(workspace, model_label, has_model).run()
    print(startup_text(workspace, model_label, has_model), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
