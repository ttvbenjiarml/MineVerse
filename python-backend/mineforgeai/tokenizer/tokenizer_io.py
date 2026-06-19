from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SimpleBPETokenizer:
    vocab: dict[str, int] = field(default_factory=dict)
    inverse_vocab: dict[int, str] = field(default_factory=dict)
    merges: list[tuple[str, str]] = field(default_factory=list)

    def train(self, texts: list[str], vocab_size: int = 128) -> None:
        chars = sorted(set("".join(texts))) or [" "]
        self.vocab = {token: index for index, token in enumerate(chars[:vocab_size])}
        self.inverse_vocab = {index: token for token, index in self.vocab.items()}

    def encode(self, text: str) -> list[int]:
        if not self.vocab:
            self.train([text])
        fallback = next(iter(self.vocab.values()))
        return [self.vocab.get(char, fallback) for char in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(self.inverse_vocab.get(token, "") for token in tokens)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"vocab": self.vocab, "merges": self.merges}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "SimpleBPETokenizer":
        data = json.loads(path.read_text(encoding="utf-8"))
        tokenizer = cls(vocab=data["vocab"], merges=[tuple(item) for item in data.get("merges", [])])
        tokenizer.inverse_vocab = {value: key for key, value in tokenizer.vocab.items()}
        return tokenizer
