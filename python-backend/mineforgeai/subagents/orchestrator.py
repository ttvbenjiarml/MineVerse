from __future__ import annotations

from mineforgeai.subagents.base import AgentResult
from mineforgeai.subagents.planner import PlannerAgent


class Orchestrator:
    def route(self, request: dict) -> AgentResult:
        return PlannerAgent().run(request)
