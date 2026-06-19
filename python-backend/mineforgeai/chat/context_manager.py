from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mineforgeai.chat.compactor import compact_messages


@dataclass
class ContextManager:
    max_messages: int = 20
    messages: list[dict] = field(default_factory=list)
    prior_summary: str = ""
    virtual_context_window_tokens: int = 131072

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def load_summary(self, summary: str) -> None:
        self.prior_summary = summary.strip()

    def token_estimate(self) -> int:
        return len(self.prior_summary.split()) + sum(len(message["content"].split()) for message in self.messages)

    def maybe_compact(self, output_dir: Path, threshold: int = 100) -> dict | None:
        if self.token_estimate() < threshold:
            return None
        return compact_messages(self.messages, self.max_messages, output_dir)

    def recent_messages(self, limit: int = 8) -> list[dict]:
        return self.messages[-limit:]
