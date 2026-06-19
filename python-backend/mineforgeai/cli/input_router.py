from __future__ import annotations

from mineforgeai.agent.natural_language_router import route_message


def route_input(text: str) -> dict:
    return route_message(text)
