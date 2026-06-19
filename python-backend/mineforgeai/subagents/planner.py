from __future__ import annotations

from mineforgeai.subagents.base import AgentResult, BaseAgent


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, request: dict) -> AgentResult:
        return AgentResult("success", "planned request", {"steps": ["research", "code", "review", "test"], **request})
