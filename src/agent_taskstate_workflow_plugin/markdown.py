from __future__ import annotations

import re
from pathlib import Path

FRONT_MATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
TITLE_PATTERN = re.compile(r"^#\s+(.*)$", re.MULTILINE)


def parse_front_matter(text: str) -> dict[str, str]:
    match = FRONT_MATTER_PATTERN.match(text)
    if match is None:
        return {}
    payload: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        payload[key.strip()] = value.split("#", 1)[0].strip()
    return payload


def title_from_text(text: str) -> str:
    match = TITLE_PATTERN.search(text)
    return match.group(1).strip() if match else ""


def read_markdown(path: Path) -> tuple[str, dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    return text, parse_front_matter(text), title_from_text(text)
