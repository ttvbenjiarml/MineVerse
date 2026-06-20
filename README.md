# MineForgeAI Omniverse — User Guide

MineForgeAI Omniverse is a local AI assistant for Minecraft development. This short guide is for end users: how to run the app, use the chat/CLI, and how the app uses a trained model when one is provided. Training instructions are intentionally omitted — see the developer docs in `python-backend/` if you need them.
---

## Quick Start — Run the app

Requirements: Python 3.10+ (recommended). Node/npm are optional unless you install the CLI package.

- Run the bundled GUI launcher (recommended):

```bash
python train.py
```

- If an npm package is installed system-wide, you can also run the `mineforge` command.

### One-command install (npm)

You can install the CLI with a single npm command. From the repository root (or when the package is published to npm):

Local install (global from current folder):

```bash
npm install -g .
# or when published: npm install -g mineforge
```

The package runs a postinstall helper that creates the Python `.venv`, installs Python dependencies, registers the backend, and can install a local model archive.

Model-backed install from npm:

```bash
npm install -g mineforge
```

When `package.json` points at your GitHub repo, the installer looks for this Release asset automatically:

```text
https://github.com/ttvbenjiarml/MineVerse/releases/latest/download/mineforge_model_latest.zip
```

Custom model URL override:

```powershell
$env:MINEFORGE_MODEL_URL = "https://github.com/ttvbenjiarml/MineVerse/releases/latest/download/mineforge_model_latest.zip"
npm install -g mineforge
```

The model ZIP must contain `model.pt`, `tokenizer.json`, and `model_config.json`. It may contain those files at the ZIP root or inside one nested folder. If no model URL is configured, the CLI still installs and uses deterministic Minecraft tools plus any remote model settings you configure later.

The first launch may create a `.venv` and install dependencies; this happens automatically.

### CI publishing from GitHub

This repository includes GitHub Actions workflows that can publish the Node package and the Python backend when a release is published or when a semver tag (for example `v1.2.3`) is pushed.

To enable automated publishing, add the following repository secrets (Settings → Secrets and variables → Actions):

- **NPM_TOKEN** — an npm automation token (from your npm account). Required for npm publishing.
- **PYPI_API_TOKEN** — a PyPI API token (optional). Required only if you want the Python backend published to PyPI.

After adding the secrets, create a GitHub Release (or push a `v*.*.*` tag) and the workflows will publish the packages.
---

## Using the model (no training required)

End users typically do not need to train anything. If a trained model is present, the app will load and use it automatically for generation. To provide or update a custom model, copy these files into the application models directory on the machine where MineForgeAI runs:

- Required files: `model.pt` (weights), `tokenizer.json`, `model_config.json`

Typical locations (the app checks these locations at startup):

- Windows: `%LOCALAPPDATA%\MineForgeAI\models\latest`
- macOS: `~/Library/Application Support/MineForgeAI/models/latest`
- Linux: `$XDG_DATA_HOME/mineforgeai/models/latest` or `~/.local/share/mineforgeai/models/latest`

After copying the files, restart MineForgeAI (run `python train.py` or the `mineforge` command). The backend will use the provided model automatically. If no model is found, MineForgeAI runs in fallback mode (still provides templates, analysis, and deterministic tools).
---

## App UI and Commands

- GUI: `python train.py` opens a compact GUI (dark mode default) with live logs and controls.
- CLI: When installed as a system command it is available as `mineforge` (optional packaging).
- Chat examples: "Create a Paper 1.21.1 plugin that adds a custom sword VFX", "Generate a Fabric mod skeleton for 1.20.1".

The GUI and CLI focus on using the local model to generate and assist; end users do not need to interact with training files.
---

## Troubleshooting

- If you expect the app to use your custom model but it still falls back, confirm the three required files are present in the `models/latest` directory for your platform and restart the app.
- If startup is slow on first run, allow the installer time to create the `.venv` and install packages.

If you need developer-level instructions (training, checkpoints, or packaging), see the developer docs in `python-backend/` or open an issue.
---

## Support & License

If you run into problems or want the developer instructions, open an issue in this repository. This project is open-source; include your preferred license in `LICENSE` (the repo already contains one — confirm before publishing).

---

If you'd like, I can add a short `CONTRIBUTING.md` and a simple GitHub Actions workflow next.

---

## Auto-download a pre-trained model

If you'd like MineForgeAI to automatically download a pre-trained model, set `MINEFORGE_MODEL_URL` to a URL or local folder/ZIP path containing the three required files (`model.pt`, `tokenizer.json`, `model_config.json`). The npm postinstall helper and `start_bot.py` both use the local models folder if the artifacts are missing.

Example (PowerShell):

```powershell
$env:MINEFORGE_MODEL_URL = "https://example.com/mineforge_model_latest.zip"
python start_bot.py
```

Example (bash):

```bash
export MINEFORGE_MODEL_URL="https://example.com/mineforge_model_latest.zip"
python start_bot.py
```

If the download succeeds, the app will use the model automatically on next launch.
# MineVerse
