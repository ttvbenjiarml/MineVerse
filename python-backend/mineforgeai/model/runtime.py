from __future__ import annotations

import json
import warnings
from typing import Generator
from dataclasses import dataclass
from pathlib import Path

from mineforgeai.hardware import detect_hardware, recommended_virtual_context_window
from mineforgeai.model.checkpointing import find_trained_model_dir, model_artifact_paths, required_model_artifact_paths
from mineforgeai.model.generation import apply_repetition_penalty, sample_next_token, top_k_top_p_filter
from mineforgeai.model.transformer import ModelConfig, create_model
from mineforgeai.tokenizer.tokenizer_io import SimpleBPETokenizer


@dataclass
class LocalModelRuntime:
    model_dir: Path
    model: object
    tokenizer: SimpleBPETokenizer
    config: ModelConfig
    device: str
    precision: str
    performance_tier: str
    preferred_profile: str = "balanced"
    virtual_context_window_tokens: int = 131072

    def generate_text(
        self,
        prompt: str,
        max_new_tokens: int = 160,
        temperature: float = 0.8,
        top_k: int = 40,
        top_p: float = 0.9,
        repetition_penalty: float = 1.08,
        profile: str | None = None,
    ) -> str:
        try:
            import torch
        except Exception as exc:
            raise RuntimeError("PyTorch is required for local inference") from exc

        self.model.eval()
        active_profile = profile or self.preferred_profile
        if active_profile == "fast":
            temperature = 0.7
            top_k = 20
            top_p = 0.85
            max_new_tokens = min(max_new_tokens, 80)
        elif active_profile == "quality":
            temperature = 0.85
            top_k = 60
            top_p = 0.95
            max_new_tokens = min(max_new_tokens, 220)
            repetition_penalty = max(repetition_penalty, 1.1)

        if self.performance_tier == "low":
            max_new_tokens = min(max_new_tokens, 96)
            top_k = min(top_k, 20)
        elif self.performance_tier == "mid":
            max_new_tokens = min(max_new_tokens, 128)
        if self.virtual_context_window_tokens <= 65536:
            max_new_tokens = min(max_new_tokens, 96)
        input_tokens = self.tokenizer.encode(prompt)
        if not input_tokens:
            input_tokens = [0]
        input_tokens = input_tokens[-self.config.context_length :]
        generated = list(input_tokens)

        autocast_enabled = self.device in {"cuda", "mps"} and self.precision in {"float16", "bfloat16"}
        autocast_dtype = torch.float16 if self.precision == "float16" else torch.bfloat16 if self.precision == "bfloat16" else None

        with torch.inference_mode():
            for _ in range(max_new_tokens):
                window = generated[-self.config.context_length :]
                input_ids = torch.tensor([window], dtype=torch.long, device=self.device)
                if autocast_enabled and autocast_dtype is not None:
                    with torch.autocast(device_type=self.device, dtype=autocast_dtype):
                        logits = self.model(input_ids)[:, -1, :]
                else:
                    logits = self.model(input_ids)[:, -1, :]
                logits = apply_repetition_penalty(logits, generated, repetition_penalty)
                logits = top_k_top_p_filter(logits, top_k=top_k, top_p=top_p)
                next_token = sample_next_token(logits, temperature=temperature)
                token_id = int(next_token.item())
                generated.append(token_id)

        decoded = self.tokenizer.decode(generated[len(input_tokens) :]).strip()
        return decoded

    def generate_text_streaming(
        self,
        prompt: str,
        max_new_tokens: int = 160,
        temperature: float = 0.8,
        top_k: int = 40,
        top_p: float = 0.9,
        repetition_penalty: float = 1.08,
        profile: str | None = None,
    ) -> Generator[str, None, None]:
        """Yield decoded text incrementally, token by token, for live streaming output."""
        try:
            import torch
        except Exception as exc:
            raise RuntimeError("PyTorch is required for local inference") from exc

        self.model.eval()
        active_profile = profile or self.preferred_profile
        if active_profile == "fast":
            temperature = 0.7
            top_k = 20
            top_p = 0.85
            max_new_tokens = min(max_new_tokens, 80)
        elif active_profile == "quality":
            temperature = 0.85
            top_k = 60
            top_p = 0.95
            max_new_tokens = min(max_new_tokens, 220)
            repetition_penalty = max(repetition_penalty, 1.1)

        if self.performance_tier == "low":
            max_new_tokens = min(max_new_tokens, 96)
            top_k = min(top_k, 20)
        elif self.performance_tier == "mid":
            max_new_tokens = min(max_new_tokens, 128)
        if self.virtual_context_window_tokens <= 65536:
            max_new_tokens = min(max_new_tokens, 96)
        input_tokens = self.tokenizer.encode(prompt)
        if not input_tokens:
            input_tokens = [0]
        input_tokens = input_tokens[-self.config.context_length :]
        generated = list(input_tokens)

        autocast_enabled = self.device in {"cuda", "mps"} and self.precision in {"float16", "bfloat16"}
        autocast_dtype = torch.float16 if self.precision == "float16" else torch.bfloat16 if self.precision == "bfloat16" else None

        prev_text = ""
        with torch.inference_mode():
            for _ in range(max_new_tokens):
                window = generated[-self.config.context_length :]
                input_ids = torch.tensor([window], dtype=torch.long, device=self.device)
                if autocast_enabled and autocast_dtype is not None:
                    with torch.autocast(device_type=self.device, dtype=autocast_dtype):
                        logits = self.model(input_ids)[:, -1, :]
                else:
                    logits = self.model(input_ids)[:, -1, :]
                logits = apply_repetition_penalty(logits, generated, repetition_penalty)
                logits = top_k_top_p_filter(logits, top_k=top_k, top_p=top_p)
                next_token = sample_next_token(logits, temperature=temperature)
                token_id = int(next_token.item())
                generated.append(token_id)
                # Decode everything so far and yield only the new characters
                full_text = self.tokenizer.decode(generated[len(input_tokens) :])
                if len(full_text) > len(prev_text):
                    yield full_text[len(prev_text):]
                    prev_text = full_text


def _load_model_config(path: Path) -> ModelConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ModelConfig(**payload)


def model_is_usable(model_dir: Path) -> bool:
    artifacts = required_model_artifact_paths(model_dir)
    return all(path.exists() for path in artifacts.values())


def load_local_model(workspace: Path) -> LocalModelRuntime | None:
    model_dir = find_trained_model_dir(workspace)
    if model_dir is None or not model_is_usable(model_dir):
        return None

    try:
        import torch
    except Exception:
        return None

    artifacts = model_artifact_paths(model_dir)
    config = _load_model_config(artifacts["config"])
    tokenizer = SimpleBPETokenizer.load(artifacts["tokenizer"])
    profile = detect_hardware()
    device = profile.device if profile.device in {"cuda", "mps"} else "cpu"
    torch.set_float32_matmul_precision("high")
    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.benchmark = True

    load_kwargs = {"map_location": device}
    if profile.virtual_memory_enabled:
        load_kwargs["mmap"] = True
    state_dict = torch.load(artifacts["weights"], **load_kwargs)
    if isinstance(state_dict, dict) and "model_state_dict" in state_dict:
        state_dict = state_dict["model_state_dict"]

    if "token_embedding.weight" in state_dict:
        config.vocab_size = state_dict["token_embedding.weight"].shape[0]
    else:
        if config.vocab_size != len(tokenizer.vocab):
            config.vocab_size = len(tokenizer.vocab)

    model = create_model(config)
    model.load_state_dict(state_dict, strict=False)
    if device in {"cuda", "mps"}:
        dtype = torch.float16 if profile.precision == "float16" else torch.bfloat16 if profile.precision == "bfloat16" else None
        model.to(device=device, dtype=dtype)
    else:
        model.to(device)
    if hasattr(torch, "compile") and device == "cuda" and profile.performance_tier in {"high", "enthusiast"}:
        try:
            model = torch.compile(model)
        except Exception:
            pass
    preferred_profile = "quality" if profile.performance_tier in {"high", "enthusiast"} else "balanced" if profile.performance_tier == "mid" else "fast"
    return LocalModelRuntime(
        model_dir=model_dir,
        model=model,
        tokenizer=tokenizer,
        config=config,
        device=device,
        precision=profile.precision,
        performance_tier=profile.performance_tier,
        preferred_profile=preferred_profile,
        virtual_context_window_tokens=recommended_virtual_context_window(profile),
    )
