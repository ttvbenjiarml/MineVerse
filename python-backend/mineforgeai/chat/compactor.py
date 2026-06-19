from __future__ import annotations

import json
from pathlib import Path

from mineforgeai.chat.summaries import summarize_messages


COMPACTION_MESSAGE = "[context compacted: saved project goals, files, decisions, and TODOs]"


def compact_messages(messages: list[dict], keep_recent: int, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_messages(messages[:-keep_recent] if keep_recent < len(messages) else messages)
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")
    with (output_dir / "messages.jsonl").open("w", encoding="utf-8") as handle:
        for message in messages:
            handle.write(json.dumps(message) + "\n")
    state = {
        "message_count": len(messages),
        "recent_kept": min(keep_recent, len(messages)),
        "summary_file": str(output_dir / "summary.md"),
        "summary_preview": summary[:500],
    }
    (output_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"summary": summary, "state": state, "notice": COMPACTION_MESSAGE}
