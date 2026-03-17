from __future__ import annotations

from stt_quiz_service.services.preprocess import split_raw_text_blocks, strip_stt_markup
from stt_quiz_service.services.stt_preprocessor import MockSTTPreprocessor


def test_mock_stt_preprocessor_canonicalizes_technical_terms():
    preprocessor = MockSTTPreprocessor()
    raw_text = (
        "<09:00:00> a1: 자바 nio 패키지에서 셀렉트 프롬 웨어 절을 같이 봅니다.\n"
        "<09:00:01> a1: 자바 io도 같이 정리합니다.\n"
    )

    processed = preprocessor.preprocess_text(raw_text=raw_text)

    assert "Java NIO" in processed
    assert "SELECT" in processed
    assert "FROM" in processed
    assert "WHERE" in processed
    assert "Java IO" in processed


def test_mock_stt_preprocessor_keeps_non_empty_lines():
    preprocessor = MockSTTPreprocessor()
    raw_text = (
        "<09:00:00> a1: 여러분 안녕하세요.\n"
        "<09:00:01> a1: 자바 io에 대해서 설명합니다.\n"
    )

    processed = preprocessor.preprocess_text(raw_text=raw_text)
    processed_lines = processed.splitlines()

    assert len(processed_lines) == 2
    assert processed_lines[0] == "여러분 안녕하세요."
    assert processed_lines[1] == "Java IO에 대해서 설명합니다."


def test_split_raw_text_blocks_preserves_order_without_semantic_segmentation():
    raw_text = "\n".join(
        [
            "<09:00:00> a1: 첫 번째 줄입니다.",
            "<09:00:01> a1: 두 번째 줄입니다.",
            "<09:00:02> a1: 세 번째 줄입니다.",
            "<09:00:03> a1: 네 번째 줄입니다.",
        ]
    )

    blocks = split_raw_text_blocks(raw_text, max_chars=45)

    assert len(blocks) >= 2
    assert blocks[0].startswith("<09:00:00> a1: 첫 번째 줄입니다.")
    assert blocks[-1].endswith("<09:00:03> a1: 네 번째 줄입니다.")


def test_strip_stt_markup_removes_timestamp_and_speaker_only():
    line = "<09:11:19> f1db1019: 여러분 안녕하세요."
    assert strip_stt_markup(line) == "여러분 안녕하세요."
