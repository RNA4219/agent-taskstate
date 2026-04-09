from __future__ import annotations

from pathlib import Path


def render_acceptance_index_markdown(acceptances: list[dict]) -> str:
    lines = [
        "# Acceptance Index",
        "",
        "| Acceptance | Task | Intent | Status | Reviewed | File |",
        "|---|---|---|---|---|---|",
    ]
    for acceptance in acceptances:
        lines.append(
            "| "
            f"{acceptance['acceptance_id']} | {acceptance['task_id']} | {acceptance['intent_id']} | "
            f"{acceptance['status']} | {acceptance['reviewed_at']} | "
            f"[{Path(acceptance['path']).name}]({acceptance['path']}) |"
        )
    lines.append("")
    return "\n".join(lines)
