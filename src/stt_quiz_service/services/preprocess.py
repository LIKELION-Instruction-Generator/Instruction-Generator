from __future__ import annotations

import re


PRACTICE_RE = re.compile(r"\bQ\s?\d+\b", re.IGNORECASE)
LINE_RE = re.compile(r"^<(?P<time>\d{2}:\d{2}:\d{2})>\s*(?P<speaker>[0-9a-z]+)?\s*:\s*(?P<text>.*)$")


def normalize_mixed_language_spacing(text: str) -> str:
    text = re.sub(r"([가-힣])([A-Za-z0-9])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z0-9])([가-힣])", r"\1 \2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_raw_text_blocks(raw_text: str, *, max_chars: int = 12000) -> list[str]:
    lines = raw_text.splitlines()
    if not lines:
        return []

    blocks: list[str] = []
    buffer: list[str] = []
    current_chars = 0

    def flush() -> None:
        nonlocal buffer, current_chars
        if not buffer:
            return
        blocks.append("\n".join(buffer).strip())
        buffer = []
        current_chars = 0

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line:
            continue
        projected = current_chars + len(line) + 1
        if buffer and projected > max_chars:
            flush()
        buffer.append(line)
        current_chars += len(line) + 1

    flush()
    return [block for block in blocks if block]


def strip_stt_markup(line: str) -> str:
    match = LINE_RE.match(line.strip())
    if match:
        return match.group("text").strip()
    return line.strip()


def sentence_split(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?…])\s+|\n+", text)
    return [normalize_mixed_language_spacing(chunk) for chunk in chunks if chunk.strip()]
