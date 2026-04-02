from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math
import re
from typing import Callable

from stt_quiz_service.config import Settings
from stt_quiz_service.schemas import ChunkDocument, DailyTermCandidate, DailyTermCandidates


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣][A-Za-z0-9가-힣_./+-]{1,}")

# kiwipiepy 품사 태그 중 기술 키워드로 의미 있는 것만 유지
# NNG: 일반명사 (모델, 어텐션, 벡터)
# NNP: 고유명사 (트랜스포머, BERT, GPT)
# SL:  외래어   (Attention, Embedding, Softmax)
# SH:  한자어
# 제외: MAG(일반부사), MAJ(접속부사), NNB(의존명사: 것/수/때), NP(대명사), VV(동사) 등
NOUN_TAGS = {"NNG", "NNP", "SL", "SH"}

GENERIC_TERMS = {
    "오늘",
    "오늘은",
    "수업",
    "강의",
    "내용",
    "부분",
    "설명",
    "설명합니다",
    "정도",
    "경우",
    "생각",
    "처리",
    "학습",
    "예제",
    "예시",
    "방법",
    "방법을",
    "사용한",
    "사용해서",
    "함께",
    "다룹니다",
}


def normalize_term(term: str) -> str:
    normalized = re.sub(r"\s+", " ", term.strip("`'\"[](){}")).strip()
    return normalized


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9가-힣]+", "", text).casefold()


def aggregate_weekly_candidates(candidate_sets: list[DailyTermCandidates], *, limit: int = 60) -> list[DailyTermCandidate]:
    merged: dict[str, DailyTermCandidate] = {}
    for candidate_set in candidate_sets:
        for candidate in candidate_set.candidates:
            key = normalize_term(candidate.term).casefold()
            if not key:
                continue
            existing = merged.get(key)
            if existing is None:
                merged[key] = DailyTermCandidate(
                    term=normalize_term(candidate.term),
                    score=candidate.score,
                    evidence_chunk_ids=list(candidate.evidence_chunk_ids),
                )
                continue
            existing.score += candidate.score
            existing.evidence_chunk_ids = list(
                dict.fromkeys(existing.evidence_chunk_ids + candidate.evidence_chunk_ids)
            )[:5]
    ranked = sorted(merged.values(), key=lambda item: (-item.score, item.term))
    return ranked[:limit]


@dataclass(slots=True)
class DailyTermCandidateExtractor:
    settings: Settings
    _keybert_model: object | None = field(default=None, init=False, repr=False)
    _embedding_device: str | None = field(default=None, init=False, repr=False)
    _kiwi_model: object | None = field(default=None, init=False, repr=False)

    def extract(
        self,
        *,
        corpus_id: str,
        week_id: str,
        cleaned_text: str,
        chunks: list[ChunkDocument],
        progress_callback: Callable[[str], None] | None = None,
    ) -> DailyTermCandidates:
        self._emit(progress_callback, "candidate extraction start")
        noun_text = self._noun_only_text(cleaned_text)
        self._emit(progress_callback, f"noun extraction done chars={len(noun_text)}")
        yake_terms = self._extract_yake(noun_text)
        self._emit(progress_callback, f"yake done terms={len(yake_terms)}")
        _model, device = self._build_keybert()
        self._emit(progress_callback, f"keybert init device={device}")
        keybert_terms = self._extract_keybert(noun_text)
        self._emit(progress_callback, f"keybert done terms={len(keybert_terms)}")
        combined = self._combine_rankings(yake_terms, keybert_terms)
        self._emit(progress_callback, f"ranking merged candidates={len(combined)}")
        enriched = self._attach_evidence(combined, chunks)
        self._emit(progress_callback, f"evidence attached candidates={len(enriched)}")
        return DailyTermCandidates(
            corpus_id=corpus_id,
            week_id=week_id,
            candidates=enriched[: self.settings.daily_term_candidate_limit],
        )

    @staticmethod
    def _emit(progress_callback: Callable[[str], None] | None, message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    @staticmethod
    def _import_yake():
        try:
            import yake
        except ModuleNotFoundError as exc:
            raise RuntimeError("yake is not installed. Install weekly topic extraction dependencies first.") from exc
        return yake

    @staticmethod
    def _import_keybert():
        try:
            from keybert import KeyBERT
        except ModuleNotFoundError as exc:
            raise RuntimeError("keybert is not installed. Install weekly topic extraction dependencies first.") from exc
        return KeyBERT

    @staticmethod
    def _import_sentence_transformer():
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install weekly topic extraction dependencies first."
            ) from exc
        return SentenceTransformer

    @staticmethod
    def _import_kiwi():
        try:
            from kiwipiepy import Kiwi
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "kiwipiepy is not installed. Install weekly topic extraction dependencies first."
            ) from exc
        return Kiwi

    def _build_kiwi(self) -> object:
        if self._kiwi_model is not None:
            return self._kiwi_model
        Kiwi = self._import_kiwi()
        self._kiwi_model = Kiwi()
        return self._kiwi_model

    def _noun_only_text(self, text: str) -> str:
        """원문에서 명사·외래어 토큰만 추출하여 공백으로 이어 붙인 텍스트를 반환한다.
        YAKE/KeyBERT 입력용. 부사·접속어·조사·어미 등은 이 단계에서 제거된다."""
        kiwi = self._build_kiwi()
        tokens = kiwi.tokenize(text)
        # 문장 경계(SF)를 개행으로 보존해 YAKE의 n-gram이 문장을 넘어가지 않도록 함
        result_lines: list[str] = []
        current_line: list[str] = []
        for token in tokens:
            if token.tag == "SF":
                if current_line:
                    result_lines.append(" ".join(current_line))
                    current_line = []
            elif token.tag in NOUN_TAGS:
                current_line.append(token.form)
        if current_line:
            result_lines.append(" ".join(current_line))
        return "\n".join(result_lines)

    @staticmethod
    def _select_embedding_device() -> str:
        try:
            import torch
        except ModuleNotFoundError:
            return "cpu"
        if torch.backends.mps.is_built() and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _build_keybert(self) -> tuple[object, str]:
        if self._keybert_model is not None and self._embedding_device is not None:
            return self._keybert_model, self._embedding_device
        KeyBERT = self._import_keybert()
        SentenceTransformer = self._import_sentence_transformer()
        device = self._select_embedding_device()
        embedder = SentenceTransformer(self.settings.keyword_embedding_model, device=device)
        self._keybert_model = KeyBERT(model=embedder)
        self._embedding_device = device
        return self._keybert_model, device

    def _extract_yake(self, cleaned_text: str) -> list[str]:
        yake = self._import_yake()
        extractor = yake.KeywordExtractor(
            lan="ko",
            n=3,
            top=max(self.settings.daily_term_candidate_limit, 40),
            dedupLim=0.9,
        )
        ranked: list[str] = []
        for term, _score in extractor.extract_keywords(cleaned_text):
            normalized = normalize_term(term)
            if self._is_valid_term(normalized):
                ranked.append(normalized)
        return list(dict.fromkeys(ranked))

    def _extract_keybert(self, cleaned_text: str) -> list[str]:
        model, _device = self._build_keybert()
        keywords = model.extract_keywords(
            cleaned_text,
            keyphrase_ngram_range=(1, 3),
            use_mmr=True,
            diversity=0.6,
            stop_words=None,
            top_n=max(self.settings.daily_term_candidate_limit, 40),
        )
        ranked: list[str] = []
        for term, _score in keywords:
            normalized = normalize_term(term)
            if self._is_valid_term(normalized):
                ranked.append(normalized)
        return list(dict.fromkeys(ranked))

    def _combine_rankings(self, yake_terms: list[str], keybert_terms: list[str]) -> list[DailyTermCandidate]:
        score_by_term: dict[str, float] = defaultdict(float)
        surface_by_term: dict[str, str] = {}
        for ranked_terms, weight in ((yake_terms, 1.0), (keybert_terms, 1.2)):
            total = max(len(ranked_terms), 1)
            for rank, term in enumerate(ranked_terms, start=1):
                key = normalize_term(term).casefold()
                surface_by_term.setdefault(key, term)
                score_by_term[key] += weight * (1.0 - ((rank - 1) / total))
        ranked = sorted(
            (
                DailyTermCandidate(term=surface_by_term[key], score=score, evidence_chunk_ids=[])
                for key, score in score_by_term.items()
            ),
            key=lambda item: (-item.score, item.term),
        )
        return ranked

    def _attach_evidence(
        self,
        candidates: list[DailyTermCandidate],
        chunks: list[ChunkDocument],
    ) -> list[DailyTermCandidate]:
        normalized_chunks = {
            chunk.chunk_id: normalize_for_match(chunk.text)
            for chunk in chunks
        }
        enriched: list[DailyTermCandidate] = []
        for candidate in candidates:
            match_key = normalize_for_match(candidate.term)
            if not match_key:
                continue
            token_parts = [normalize_for_match(token) for token in TOKEN_RE.findall(candidate.term)]
            scored_hits: list[tuple[float, str]] = []
            for chunk in chunks:
                haystack = normalized_chunks[chunk.chunk_id]
                score = 0.0
                if match_key and match_key in haystack:
                    score += 5.0
                    score += haystack.count(match_key)
                if token_parts:
                    overlap = sum(1 for token in token_parts if token and token in haystack)
                    score += overlap
                if score <= 0:
                    continue
                scored_hits.append((score, chunk.chunk_id))
            if not scored_hits:
                continue
            evidence_chunk_ids = [chunk_id for _, chunk_id in sorted(scored_hits, reverse=True)[:3]]
            enriched.append(
                candidate.model_copy(update={"evidence_chunk_ids": evidence_chunk_ids})
            )
        return enriched

    @staticmethod
    def _is_valid_term(term: str) -> bool:
        if len(term) < 2:
            return False
        if term in GENERIC_TERMS:
            return False
        if term.isdigit():
            return False
        tokens = [token.casefold() for token in TOKEN_RE.findall(term)]
        if not tokens:
            return False
        # 반복 단어 포함 n-gram 차단 ("테이블 EMP 테이블" 등)
        if len(tokens) != len(set(tokens)):
            return False
        if tokens[0] in GENERIC_TERMS or tokens[-1] in GENERIC_TERMS:
            return False
        generic_count = sum(token in GENERIC_TERMS for token in tokens)
        if generic_count and generic_count >= max(1, len(tokens) // 2):
            return False
        alpha_num_ratio = sum(ch.isalnum() or ("가" <= ch <= "힣") for ch in term) / max(len(term), 1)
        return alpha_num_ratio >= 0.6 and not math.isnan(alpha_num_ratio)
