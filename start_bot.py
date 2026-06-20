"""
start_bot.py - minimal launcher that ensures dependencies and starts the CLI

This script will:
- try to pip install python requirements (cpu/cuda/rocm) based on detected GPU
- run `npm install` if package.json exists
- launch the node `mineforge` CLI wrapper (bin/mineforge.js) which in turn
  launches the Python backend

It is a convenience wrapper to get the workspace running quickly.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import shutil
import re
import urllib.request
import tempfile
import zipfile
import os
import json

ROOT = Path(__file__).parent
PY_BACKEND = ROOT / "python-backend"
VENV_DIR = ROOT / ".venv"
REQUIRED_MODEL_FILES = ("model.pt", "tokenizer.json", "model_config.json")


def run(cmd, **kwargs):
    print(f"> {' '.join(cmd)}")
    subprocess.check_call(cmd, **kwargs)


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def create_venv() -> None:
    if VENV_DIR.exists():
        return
    print(f"Creating virtualenv at {VENV_DIR}")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])


def pip_install_requirements():
    create_venv()
    vpython = str(_venv_python())
    # choose requirements file heuristically
    if (PY_BACKEND / "requirements-cuda.txt").exists():
        req = PY_BACKEND / "requirements-cuda.txt"
    elif (PY_BACKEND / "requirements-rocm.txt").exists():
        req = PY_BACKEND / "requirements-rocm.txt"
    else:
        req = PY_BACKEND / "requirements.txt"
    print(f"Installing Python requirements from {req} into venv")
    run([vpython, "-m", "pip", "install", "-U", "pip"])  # upgrade pip
    run([vpython, "-m", "pip", "install", "-r", str(req)])
    # ensure numpy is installed (some torch builds rely on numpy being present)
    try:
        run([vpython, "-m", "pip", "install", "numpy"])
    except Exception:
        pass


def npm_install():
    pkg = ROOT / "package.json"
    if not pkg.exists():
        return
    print("Running npm install for Node CLI")
    node_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not node_cmd:
        print("npm not found on PATH. Please install Node.js and npm.")
        return
    # run npm install and capture output so we can auto-approve install scripts if needed
    try:
        print(f"> {node_cmd} install")
        proc = subprocess.run([node_cmd, "install"], cwd=str(ROOT), capture_output=True, text=True)
        out = (proc.stdout or "") + (proc.stderr or "")
        print(out)
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, [node_cmd, "install"], output=out)

        # look for packages with install scripts pending approval
        pending: list[str] = []
        for line in out.splitlines():
            # match lines like: "npm warn allow-scripts   esbuild@0.28.1 (install: (install scripts present))"
            m = re.search(r"\s*([^\s]+@[^\s]+)\s+\(install:\s*\(install scripts present\)\)", line)
            if m:
                pending.append(m.group(1))

        if pending:
            pending = list(dict.fromkeys(pending))
            print(f"Pending install-scripts detected for packages: {pending}")
            # Try bulk approval first
            try:
                print(f"> {node_cmd} approve-scripts --allow-scripts-pending")
                proc_a = subprocess.run([node_cmd, "approve-scripts", "--allow-scripts-pending"], cwd=str(ROOT))
                if proc_a.returncode == 0:
                    print("Bulk approval succeeded")
                else:
                    raise subprocess.CalledProcessError(proc_a.returncode, [node_cmd, "approve-scripts", "--allow-scripts-pending"])
            except Exception:
                print("Bulk approval failed; attempting per-package approval")
                for pkgname in pending:
                    pkg_short = pkgname.split("@")[0]
                    try:
                        subprocess.check_call([node_cmd, "approve-scripts", pkg_short], cwd=str(ROOT))
                    except Exception as exc:
                        print(f"Failed to approve scripts for {pkgname}: {exc}")
            # rerun npm install to ensure scripts are executed
            print(f"> {node_cmd} install (rerun after approvals)")
            proc2 = subprocess.run([node_cmd, "install"], cwd=str(ROOT))
            if proc2.returncode != 0:
                raise subprocess.CalledProcessError(proc2.returncode, [node_cmd, "install"])
    except subprocess.CalledProcessError as exc:
        print(f"npm install failed: {exc}")


def _model_artifacts_present() -> bool:
    """Return True if required model artifacts exist in the user models latest dir."""
    try:
        # import backend helper to find the user models dir and artifact names
        sys.path.insert(0, str(PY_BACKEND))
        from mineforgeai.paths import latest_model_dir
        from mineforgeai.model.checkpointing import required_model_artifact_paths

        latest = latest_model_dir()
        artifacts = required_model_artifact_paths(latest)
        return all(p.exists() for p in artifacts.values())
    except Exception:
        return False


def _required_model_files_present(directory: Path) -> bool:
    return all((directory / filename).is_file() and (directory / filename).stat().st_size > 0 for filename in REQUIRED_MODEL_FILES)


def _find_model_artifact_dir(source: Path) -> Path | None:
    if _required_model_files_present(source):
        return source
    for current, dirs, _files in os.walk(source):
        current_path = Path(current)
        if _required_model_files_present(current_path):
            return current_path
        # Model release zips should be shallow. Avoid scanning large unrelated folders forever.
        rel_parts = current_path.relative_to(source).parts
        if len(rel_parts) >= 3:
            dirs[:] = []
    return None


def _copy_model_artifacts(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for filename in REQUIRED_MODEL_FILES:
        shutil.copy2(source / filename, dest / filename)
    if (source / "state.json").is_file():
        shutil.copy2(source / "state.json", dest / "state.json")
    for filename in ("tokenizer.json", "model_config.json"):
        json.loads((dest / filename).read_text(encoding="utf-8"))


def _install_model_source(source: str, dest: Path) -> bool:
    """Install model artifacts from a URL, local zip, or local folder."""
    with tempfile.TemporaryDirectory(prefix="mineforge_model_") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        source_path = Path(source).expanduser()

        try:
            if source.startswith(("http://", "https://")):
                downloaded = tmp_dir / "model-download"
                print(f"Downloading model from: {source}")
                urllib.request.urlretrieve(source, downloaded)
                source_path = downloaded

            if source_path.is_dir():
                artifact_dir = _find_model_artifact_dir(source_path)
            elif source_path.is_file() and zipfile.is_zipfile(source_path):
                extract_dir = tmp_dir / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(source_path, "r") as archive:
                    archive.extractall(extract_dir)
                artifact_dir = _find_model_artifact_dir(extract_dir)
            else:
                raise FileNotFoundError(f"Model source is not a folder or zip archive: {source}")

            if artifact_dir is None:
                raise FileNotFoundError("Model source does not contain model.pt, tokenizer.json, and model_config.json")

            _copy_model_artifacts(artifact_dir, dest)
            return True
        except Exception as exc:
            print(f"Model install failed: {exc}")
            return False


def download_model_if_configured():
    """If an environment variable `MINEFORGE_MODEL_URL` is set and model
    artifacts are missing, attempt to download and extract the model archive.
    """
    env_url = os.environ.get("MINEFORGE_MODEL_URL")
    if not env_url:
        return
    if _model_artifacts_present():
        print("Model artifacts already present; skipping auto-download.")
        return
    try:
        sys.path.insert(0, str(PY_BACKEND))
        from mineforgeai.paths import latest_model_dir

        latest = latest_model_dir()
        print(f"Auto-downloading model to: {latest}")
        ok = _install_model_source(env_url, latest)
        if ok:
            print("Model download/extract completed.")
        else:
            print("Model download failed; please check MINEFORGE_MODEL_URL and try again.")
    except Exception as exc:
        print(f"Auto-download failed: {exc}")


def launch_tui():
    vpython = str(_venv_python())
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PY_BACKEND)
    print("Launching MineVerse TUI...")
    run([vpython, "-m", "mineforgeai.cli.tui"], env=env)


def main():
    # allow a CI/smoke test mode where we skip heavy installs
    ci = os.environ.get("MINEFORGE_CI", "0") == "1" or "--ci" in sys.argv
    if not ci:
        try:
            pip_install_requirements()
        except Exception as exc:
            print(f"Warning: pip install failed: {exc}")
        try:
            npm_install()
        except Exception as exc:
            print(f"Warning: npm install failed: {exc}")
        # attempt model auto-download if configured
        try:
            download_model_if_configured()
        except Exception as exc:
            print(f"Warning: model auto-download failed: {exc}")
    else:
        print("CI mode: skipping installs and launching smoke test")

    # finally launch tui by default (or smoke test)
    try:
        if ci:
            # in CI we simply check the python backend imports
            run([str(_venv_python()), "-c", "import sys; sys.exit(0)"])
        else:
            launch_tui()
    except KeyboardInterrupt:
        print("Exiting...")


if __name__ == "__main__":
    main()
