from __future__ import annotations

from pathlib import Path

from mineforgeai.tokenizer.tokenizer_io import SimpleBPETokenizer


def train_tokenizer(texts: list[str], output: Path) -> SimpleBPETokenizer:
    tokenizer = SimpleBPETokenizer()
    tokenizer.train(texts)
    tokenizer.save(output)
    return tokenizer
