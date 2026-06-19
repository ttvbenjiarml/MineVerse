from __future__ import annotations

from mineforgeai.data.redaction import redact_text


def clean_text(text: str) -> str:
    return redact_text(text).strip()
