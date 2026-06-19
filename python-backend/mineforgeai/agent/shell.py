from __future__ import annotations

import re


DANGEROUS_PATTERNS = [
    re.compile(r"rm\s+-rf\s+\*", re.IGNORECASE),
    re.compile(r"rm\s+-rf\s+/$", re.IGNORECASE),
    re.compile(r"del\s+/s", re.IGNORECASE),
    re.compile(r"format(\s|$)", re.IGNORECASE),
    re.compile(r"shutdown", re.IGNORECASE),
    re.compile(r"curl.+\|\s*sh", re.IGNORECASE),
]


def is_safe_command(command: str) -> bool:
    return not any(pattern.search(command) for pattern in DANGEROUS_PATTERNS)
