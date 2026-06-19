from __future__ import annotations

from dataclasses import dataclass, field

from mineforgeai.chat.context_manager import ContextManager


@dataclass
class ChatSession:
    context: ContextManager = field(default_factory=ContextManager)
    web_enabled: bool = False
