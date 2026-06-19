from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentResult:
    status: str
    summary: str
    payload: dict


class BaseAgent:
    name = "base"

    def run(self, request: dict) -> AgentResult:
        return AgentResult(status="success", summary=f"{self.name} completed", payload=request)
