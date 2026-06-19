from __future__ import annotations


def clarification_question(question: str, options: list[str]) -> str:
    if len(options) != 3:
        raise ValueError("clarification questions require exactly 3 suggested choices")
    lines = ["I need one detail to make this accurate:", "", question, ""]
    for index, option in enumerate(options, start=1):
        lines.append(f"{index}. {option}")
    lines.append("4. Type my own answer")
    return "\n".join(lines)
