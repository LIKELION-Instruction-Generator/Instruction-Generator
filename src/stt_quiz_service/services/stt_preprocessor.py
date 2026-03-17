from __future__ import annotations

from dataclasses import dataclass
import os
import re
import time
from typing import Callable, Protocol

from google import genai
from google.genai import types
import httpx

from stt_quiz_service.config import Settings
from stt_quiz_service.prompts import read_prompt_section
from stt_quiz_service.services.preprocess import normalize_mixed_language_spacing, split_raw_text_blocks, strip_stt_markup


TECHNICAL_TERM_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b자바\s*nio\b", re.IGNORECASE), "Java NIO"),
    (re.compile(r"\b자바\s*io\b", re.IGNORECASE), "Java IO"),
    (re.compile(r"\b자바\b"), "Java"),
    (re.compile(r"\b에이피아이\b", re.IGNORECASE), "API"),
    (re.compile(r"\b에이치티티피에스\b", re.IGNORECASE), "HTTPS"),
    (re.compile(r"\b에이치티티피\b", re.IGNORECASE), "HTTP"),
    (re.compile(r"\b디비\b", re.IGNORECASE), "DB"),
    (re.compile(r"\b엔 아이 오\b", re.IGNORECASE), "NIO"),
    (re.compile(r"\b셀렉트\b", re.IGNORECASE), "SELECT"),
    (re.compile(r"\b프롬\b", re.IGNORECASE), "FROM"),
    (re.compile(r"\b웨어\b", re.IGNORECASE), "WHERE"),
    (re.compile(r"\b그룹\s*바이\b", re.IGNORECASE), "GROUP BY"),
    (re.compile(r"\b오더\s*바이\b", re.IGNORECASE), "ORDER BY"),
    (re.compile(r"\b크리에이트\s*뷰\b", re.IGNORECASE), "CREATE VIEW"),
    (re.compile(r"\b크리에이트\s*테이블\b", re.IGNORECASE), "CREATE TABLE"),
    (re.compile(r"\b이너\s*조인\b", re.IGNORECASE), "INNER JOIN"),
    (re.compile(r"\b레프트\s*조인\b", re.IGNORECASE), "LEFT JOIN"),
    (re.compile(r"\b라이트\s*조인\b", re.IGNORECASE), "RIGHT JOIN"),
    (re.compile(r"\b조인\b", re.IGNORECASE), "JOIN"),
]


class STTPreprocessor(Protocol):
    model_name: str

    def preprocess_text(
        self,
        *,
        raw_text: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str: ...


@dataclass(slots=True)
class MockSTTPreprocessor:
    model_name: str = "mock-stt-preprocessor"

    def preprocess_text(
        self,
        *,
        raw_text: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        cleaned_lines: list[str] = []
        for raw_line in raw_text.splitlines():
            text = strip_stt_markup(raw_line)
            if not text:
                continue
            cleaned_lines.append(_canonicalize_line(text))
        return "\n".join(cleaned_lines).strip()


class PydanticAISTTPreprocessor:
    def __init__(self, settings: Settings, *, model_name: str | None = None):
        self.model_name = model_name or settings.preprocess_model
        self.block_chars = max(1000, settings.preprocess_block_chars)
        self.max_retries = 4
        self.system_prompt = read_prompt_section("STT Preprocessing System Prompt")
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is required for STT preprocessing")
        self.client = genai.Client(api_key=api_key)

    def preprocess_text(
        self,
        *,
        raw_text: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        blocks = split_raw_text_blocks(raw_text, max_chars=self.block_chars)
        normalized_blocks: list[str] = []
        for block_index, block in enumerate(blocks, start=1):
            if progress_callback:
                progress_callback(f"block {block_index}/{len(blocks)} start chars={len(block)}")
            normalized_text = self._run_block_with_retry(
                raw_text_block=block,
                block_index=block_index,
                block_count=len(blocks),
                progress_callback=progress_callback,
            )
            if not normalized_text:
                normalized_text = block.strip()
            normalized_blocks.append(normalized_text)
            if progress_callback:
                progress_callback(
                    f"block {block_index}/{len(blocks)} done out_chars={len(normalized_text)}"
                )
        return "\n".join(block for block in normalized_blocks if block).strip()

    def _run_block_with_retry(
        self,
        *,
        raw_text_block: str,
        block_index: int,
        block_count: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        prompt = self._build_prompt(
            raw_text_block=raw_text_block,
            block_index=block_index,
            block_count=block_count,
        )
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name.replace("google-gla:", ""),
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.2,
                    ),
                )
                return _normalize_plain_text_response(response.text or "")
            except Exception as exc:
                last_exc = exc
                body_text = str(exc).upper()
                if (
                    "503" not in body_text
                    and "UNAVAILABLE" not in body_text
                    and not isinstance(exc, (httpx.ReadTimeout, httpx.RemoteProtocolError))
                ):
                    raise
                if attempt == self.max_retries:
                    raise
                if progress_callback:
                    progress_callback(
                        f"block {block_index}/{block_count} retry {attempt}/{self.max_retries} reason={exc.__class__.__name__}"
                    )
                time.sleep(min(2**attempt, 20))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("STT preprocessing failed without a captured exception")

    @staticmethod
    def _build_prompt(
        *,
        raw_text_block: str,
        block_index: int,
        block_count: int,
    ) -> str:
        return (
            f"block_index={block_index}\n"
            f"block_count={block_count}\n"
            "raw_text_block=\n"
            f"{raw_text_block}"
        )


def _normalize_plain_text_response(text: str) -> str:
    normalized = text.strip()
    normalized = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", normalized)
    normalized = re.sub(r"\s*```$", "", normalized)
    normalized = re.sub(r"\[cite:\s*\d+\]", "", normalized, flags=re.IGNORECASE)
    return normalized.strip()


def _canonicalize_line(text: str) -> str:
    normalized = normalize_mixed_language_spacing(text)
    for pattern, replacement in TECHNICAL_TERM_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(
        r"((?:[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*))\s+(?=(은|는|이|가|을|를|에|의|와|과|로|으로))",
        r"\1",
        normalized,
    )
    normalized = re.sub(r"([`(])\s+", r"\1", normalized)
    normalized = re.sub(r"\s+([`),.])", r"\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
