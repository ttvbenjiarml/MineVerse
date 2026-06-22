from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import time
from pathlib import Path

from mineforgeai.paths import latest_model_dir, user_data_dir
from mineforgeai.model.transformer import MODEL_PRESETS


@dataclass
class TrainingPlan:
    hours: float
    resume: bool = True
    target_domains: tuple[str, ...] = (
        "paper_plugins",
        "spigot_plugins",
        "bukkit_plugins",
        "fabric_mods",
        "forge_mods",
        "neoforge_mods",
        "quilt_mods",
        "velocity_plugins",
        "bungee_plugins",
        "sponge_plugins",
        "datapacks",
        "resourcepacks",
        "gradle_projects",
        "crash_logs",
        "mappings",
        "generated_minecraft_summaries",
        "user_projects",
    )


def plan_training(hours: float) -> TrainingPlan:
    return TrainingPlan(hours=hours, resume=True)


def stop_time_from_hours(hours: float):
    return datetime.now(UTC) + timedelta(hours=hours)


def write_training_plan(hours: float, workspace: Path | None = None, resume: bool = True) -> Path:
    plan = plan_training(hours)
    plan.resume = resume
    base_dir = latest_model_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hours": plan.hours,
        "resume": plan.resume,
        "target_domains": list(plan.target_domains),
        "user_data_dir": str(user_data_dir()),
        "workspace": str(workspace) if workspace else None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    output = base_dir / "training_plan.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (base_dir / "model_config.json").write_text(json.dumps({"vocab_size": 256, "dropout": 0.1, **MODEL_PRESETS["tiny"]}, indent=2), encoding="utf-8")
    return output


def _remove_existing_training_files(base_dir: Path) -> None:
    for name in ("checkpoint.pt", "model.pt", "tokenizer.json", "model_config.json", "state.json", "training_plan.json", "PAUSED"):
        path = base_dir / name
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def _load_model_config(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    # import here to avoid heavy imports at module import time
    from mineforgeai.model.transformer import ModelConfig

    return ModelConfig(**payload)


def _collect_texts(workspace: Path | None, target_domains: tuple[str, ...]) -> list[str]:
    texts: list[str] = []
    if workspace is None:
        return texts
    # gather a small set of text files from the workspace
    allowed_exts = {".java", ".kt", ".kts", ".gradle", ".yaml", ".yml", ".json", ".txt", ".md", ".py", ".properties", ".xml"}
    max_chars = 200_000
    try:
        for path in Path(workspace).rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in allowed_exts:
                continue
            try:
                txt = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not txt.strip():
                continue
            texts.append(txt)
            if sum(len(t) for t in texts) > max_chars:
                break
    except Exception:
        pass
    return texts


def run_training(hours: float, workspace: Path | None = None, resume: bool = True) -> Path:
    """Train for the requested number of additional hours.

    By default, training resumes from the latest checkpoint or saved weights and
    adds another session. Passing ``resume=False`` clears the latest run first.
    """
    plan = plan_training(hours)
    plan.resume = resume
    # ensure plan and default model config are written
    base_dir = latest_model_dir()
    if not resume:
        _remove_existing_training_files(base_dir)
    plan_path = write_training_plan(hours, workspace, resume=resume)

    # load model config
    config_path = base_dir / "model_config.json"
    config = _load_model_config(config_path)

    # prepare tokenizer
    tokenizer_path = base_dir / "tokenizer.json"
    try:
        from mineforgeai.tokenizer.tokenizer_io import SimpleBPETokenizer
        from mineforgeai.tokenizer.train_tokenizer import train_tokenizer
    except Exception:
        raise

    if not tokenizer_path.exists():
        texts = _collect_texts(workspace, plan.target_domains)
        if not texts:
            texts = ["Hello MineForgeAI. This is a tiny synthetic training corpus."]
        tokenizer = train_tokenizer(texts, tokenizer_path)
    else:
        tokenizer = SimpleBPETokenizer.load(tokenizer_path)

    # try importing torch; if unavailable, bail out but keep plan saved
    try:
        import torch
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PyTorch is required to run training") from exc

    # create model
    from mineforgeai.model.transformer import create_model
    from mineforgeai.hardware import detect_hardware
    from mineforgeai.model.checkpointing import model_artifact_paths
    from datetime import datetime as _dt

    profile = detect_hardware()
    device = profile.device if profile.device in {"cuda", "mps"} else "cpu"

    checkpoint_path = base_dir / "checkpoint.pt"
    if resume and checkpoint_path.exists():
        try:
            ck = torch.load(checkpoint_path, map_location="cpu")
            state_dict = ck.get("model_state_dict", ck)
            if "token_embedding.weight" in state_dict:
                config.vocab_size = state_dict["token_embedding.weight"].shape[0]
        except Exception:
            pass
    elif resume and (base_dir / "model.pt").exists():
        try:
            weights = torch.load(base_dir / "model.pt", map_location="cpu")
            if "token_embedding.weight" in weights:
                config.vocab_size = weights["token_embedding.weight"].shape[0]
        except Exception:
            pass

    model = create_model(config)

    # checkpoint/state helpers
    artifacts = model_artifact_paths(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = base_dir / "checkpoint.pt"
    state_path = artifacts["state"]
    pause_flag = base_dir / "PAUSED"

    # load checkpoint and previous state if present
    iters = 0
    optimizer = None
    previous_seconds_trained = 0.0
    if resume and state_path.exists():
        try:
            prev_state = json.loads(state_path.read_text(encoding="utf-8"))
            previous_seconds_trained = float(prev_state.get("seconds_trained", 0.0))
        except Exception:
            previous_seconds_trained = 0.0

    loaded_from = "fresh model"
    if resume and checkpoint_path.exists():
        try:
            ck = torch.load(checkpoint_path, map_location=device)
            model.load_state_dict(ck.get("model_state_dict", ck))
            iters = int(ck.get("iterations", 0))
            previous_seconds_trained = float(ck.get("seconds_trained", previous_seconds_trained))
            opt_state = ck.get("optimizer_state_dict")
            if opt_state is not None:
                optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
                try:
                    optimizer.load_state_dict(opt_state)
                except Exception:
                    optimizer = None
            loaded_from = str(checkpoint_path)
        except Exception:
            # ignore and start fresh
            iters = 0
    elif resume and artifacts["weights"].exists():
        try:
            weights = torch.load(artifacts["weights"], map_location=device)
            model.load_state_dict(weights)
            loaded_from = str(artifacts["weights"])
        except Exception:
            loaded_from = "fresh model"

    print(f"Training source: {loaded_from}", flush=True)

    # move model to device
    if device in {"cuda", "mps"}:
        try:
            dtype = torch.float16 if profile.precision == "float16" else torch.bfloat16 if profile.precision == "bfloat16" else None
            if dtype is not None:
                model.to(device=device, dtype=dtype)
            else:
                model.to(device=device)
        except Exception:
            model.to(device)
    else:
        model.to(device)

    # prepare token stream
    all_tokens: list[int] = []
    max_tokens = 100_000
    for txt in _collect_texts(workspace, plan.target_domains):
        all_tokens.extend(tokenizer.encode(txt))
        if len(all_tokens) >= max_tokens:
            break
    # fallback synthetic tokens if not enough data
    if len(all_tokens) < (config.context_length + 1):
        vocab_size = max(2, len(tokenizer.vocab))
        import random

        all_tokens = [random.randrange(0, vocab_size) for _ in range((config.context_length + 1) * 10)]

    seq_len = config.context_length
    window = seq_len + 1
    sequences = []
    for i in range(0, len(all_tokens) - window + 1, window):
        chunk = all_tokens[i : i + window]
        inp = chunk[:-1]
        tgt = chunk[1:]
        sequences.append((inp, tgt))

    if not sequences:
        raise RuntimeError("No training sequences available")

    # convert to tensors
    inputs = torch.tensor([s[0] for s in sequences], dtype=torch.long)
    targets = torch.tensor([s[1] for s in sequences], dtype=torch.long)

    dataset = torch.utils.data.TensorDataset(inputs, targets)
    batch_size = min(8, max(1, len(dataset)))
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    if optimizer is None:
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss()

    requested_hours = hours
    requested_seconds = max(0.0, requested_hours * 3600.0)
    stop_at = datetime.now(UTC) + timedelta(seconds=requested_seconds)
    vocab_size = config.vocab_size

    # track active session time so we can accumulate seconds_trained across runs
    session_start = time.monotonic()
    session_seconds = 0.0

    def save_checkpoint(paused: bool, completed: bool = False) -> None:
        nonlocal session_start, session_seconds
        now = time.monotonic()
        session_seconds += now - session_start
        session_start = now
        total_seconds = previous_seconds_trained + session_seconds
        torch.save({
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict() if optimizer is not None else None,
            "iterations": iters,
            "seconds_trained": total_seconds,
        }, checkpoint_path)
        state = {
            "trained_at": _dt.now(UTC).isoformat(),
            "hours_requested": requested_hours,
            "session_seconds": session_seconds,
            "seconds_trained": total_seconds,
            "iterations": iters,
            "paused": paused,
            "completed": completed,
            "resume": resume,
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Training loop with checkpointing and pause flag handling
    try:
        while datetime.now(UTC) < stop_at:
            # if pause flag present, write final checkpoint and exit gracefully
            if pause_flag.exists():
                print("Pause flag detected. Saving checkpoint and exiting.", flush=True)
                save_checkpoint(paused=True)
                print("Checkpoint saved. Exiting.", flush=True)
                return base_dir

            for batch_inputs, batch_targets in dataloader:
                batch_inputs = batch_inputs.to(device)
                batch_targets = batch_targets.to(device)
                model.train()
                logits = model(batch_inputs)
                # logits: [batch, seq_len, vocab]
                loss = loss_fn(logits.view(-1, vocab_size), batch_targets.view(-1))
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                iters += 1
                if iters % 10 == 0:
                    print(f"iter={iters} loss={loss.item():.4f}", flush=True)
                # periodic checkpoint every 200 iters
                if iters % 200 == 0:
                    try:
                        save_checkpoint(paused=False)
                        print(f"Checkpoint saved at iter={iters}", flush=True)
                    except Exception as exc:
                        print(f"Failed to save checkpoint: {exc}", flush=True)

                if datetime.now(UTC) >= stop_at:
                    break
    except KeyboardInterrupt:
        print("Training interrupted by user", flush=True)

    # final save on completion
    try:
        torch.save(model.state_dict(), artifacts["weights"])
    except Exception:
        # fallback: save CPU state dict
        torch.save({k: v.cpu() for k, v in model.state_dict().items()}, artifacts["weights"])

    tokenizer.save(artifacts["tokenizer"])
    try:
        save_checkpoint(paused=False, completed=True)
    except Exception as exc:
        print(f"Failed to save final checkpoint: {exc}", flush=True)

    print(f"Training complete. Artifacts saved to: {base_dir}", flush=True)
    return base_dir
