from __future__ import annotations

import re


PATTERNS = [
    (re.compile(r"[A-Za-z0-9_\-]{24}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27}"), "[REDACTED_DISCORD_TOKEN]"),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s]+)"), r"\1[REDACTED_API_KEY]"),
]


def redact_text(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
