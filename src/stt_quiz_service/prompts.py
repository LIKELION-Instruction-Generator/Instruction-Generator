from __future__ import annotations

from pathlib import Path
import re


PROMPT_PATH = Path(__file__).resolve().parents[2] / "docs" / "llm_prompts.md"


def read_prompt_section(section_title: str) -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    pattern = rf"^## {re.escape(section_title)}\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"Prompt section not found: {section_title}")
    return match.group(1).strip()
