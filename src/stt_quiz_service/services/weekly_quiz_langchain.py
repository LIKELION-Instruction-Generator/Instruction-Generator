from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import hashlib
from itertools import combinations
import os
import re
from typing import Callable

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text

try:
    from langsmith import traceable
except Exception:  # pragma: no cover - optional tracing
    def traceable(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

from stt_quiz_service.config import Settings
from stt_quiz_service.schemas import (
    ALLOWED_LEARNING_GOAL_ENDINGS,
    TopicAxis,
    WeeklyQuizItem,
    WeeklyQuizSet,
    WeeklySelection,
    WeeklyTopicSet,
)
from stt_quiz_service.storage.repository import CorpusSelection, Repository
from stt_quiz_service.services.topic_extraction import normalize_term


PROFILE_SEQUENCE = ["basic_eval_4", "review_5", "basic_eval_4", "review_5", "retest_5"]
PROFILE_CHOICE_COUNT = {
    "basic_eval_4": 4,
    "review_5": 5,
    "retest_5": 5,
}
PROFILE_HINTS = {
    "basic_eval_4": "핵심 개념 정의와 기본 역할",
    "review_5": "사용 흐름과 연결 관계",
    "retest_5": "핵심 특징과 구분 포인트",
}
QUESTION_STEM_GUIDANCE = {
    "definition": "핵심 개념이나 정의를 묻는 질문 형식",
    "relationship": "개념 사이의 관계나 연결을 묻는 질문 형식",
    "application": "용도나 활용 맥락을 묻는 질문 형식",
    "condition": "조건이나 규칙을 묻는 질문 형식",
    "comparison": "차이점이나 구분 포인트를 묻는 질문 형식",
}
ABSENCE_PATTERNS = (
    "언급되지",
    "포함되어 있지",
    "직접적으로 설명되지",
    "자료에 없다",
    "등장하지",
    "다루지 않",
    "명시되어 있지",
    "설명되지 않",
    "없으므로",
)
NEGATION_EVIDENCE_MARKERS = (
    "아니다",
    "않는다",
    "없다",
    "불가",
    "금지",
    "제외",
    "지원하지",
)
UNRELATED_KEYWORDS = {
    "html",
    "css",
    "javascript",
    "frontend",
    "front-end",
    "디자인패턴",
    "옵저버패턴",
    "전략패턴",
    "데코레이터패턴",
    "파사드패턴",
}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+#-]*|[0-9]+(?:\.[0-9]+)?|[가-힣]{2,}")
SNIPPET_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=다)\s+|(?<=요)\s+")
BACKTICK_RE = re.compile(r"`([^`]+)`")
GROUNDING_STOPWORDS = {
    "다음",
    "가장",
    "적절한",
    "정확한",
    "설명",
    "설명한",
    "문장",
    "문장을",
    "강의",
    "내용",
    "무엇",
    "무엇입니까",
    "관련",
    "대한",
    "특징",
    "특징을",
    "핵심",
    "기본",
    "올바른",
    "고르시오",
    "알맞은",
    "설명과",
    "일치하는",
    "함께",
    "정확히",
    "맞는",
    "합니다",
    "있습니다",
    "고른",
    "고르기",
    "것",
    "경우",
    "방식",
    "의미",
    "설명으로",
    "동안",
    "따라서",
    "동시",
    "여러",
    "모두",
    "해당",
    "사용",
    "처리",
    "작업",
    "완료",
    "허용",
    "접근",
}
QUESTION_FOCUS_STOPWORDS = GROUNDING_STOPWORDS | {
    "사항",
    "사항으로",
    "주의",
    "주의해야",
    "설정",
    "설정할",
    "개념",
    "이유",
    "무엇인가요",
    "무엇인가",
    "주요",
}
KOREAN_TOKEN_SUFFIXES = (
    "으로부터",
    "이라고",
    "이라고는",
    "입니다",
    "입니까",
    "합니다",
    "한다",
    "하는",
    "하며",
    "하여",
    "했던",
    "처럼",
    "까지",
    "부터",
    "으로",
    "에서",
    "에게",
    "와의",
    "과의",
    "처럼",
    "도록",
    "하게",
    "하지",
    "되고",
    "되는",
    "되지",
    "거나",
    "에는",
    "에는",
    "에는",
    "으로는",
    "에서는",
    "와",
    "과",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "도",
    "만",
)
LEARNING_GOAL_STOPWORDS = GROUNDING_STOPWORDS | {
    "이해한다",
    "설명할",
    "설명할수있다",
    "구분할",
    "구분할수있다",
    "작성할",
    "작성할수있다",
    "활용할",
    "활용할수있다",
    "의미",
    "관계",
    "특징",
    "차이",
    "규칙",
    "구문",
    "맥락",
    "방법",
}
GENERIC_LEARNING_GOAL_PATTERNS = (
    "기본 표현",
    "관련된",
    "전반적인",
)
RAW_COPY_LIMITS = {
    "claim": (35, 0.92),
    "option": (30, 0.9),
    "answer": (30, 0.9),
    "explanation": (70, 0.82),
}


class ClaimRecord(BaseModel):
    claim_text: str
    concept_tags: list[str] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class ClaimBatch(BaseModel):
    claims: list[ClaimRecord] = Field(default_factory=list)


class QuizItemDraft(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    answer_text: str
    explanation: str
    learning_goal: str


@dataclass(slots=True)
class ClaimCandidate:
    corpus_id: str
    source_date: str
    axis: TopicAxis
    question_profile: str
    choice_count: int
    documents: list[Document]
    retrieved_chunk_ids: list[str]
    claim_text: str
    concept_tags: list[str]
    evidence_chunk_ids: list[str]
    focus_terms: list[str]
    primary_focus: str
    tuple_key: str
    claim_key: str
    stem_style: str = "definition"
    slot_index: int = 0


@traceable(run_type="chain", name="weekly_quiz_rag_build_vector_store")
def _build_vector_store(settings: Settings, embeddings: OpenAIEmbeddings) -> PGVector:
    embedding_length = 1536 if settings.openai_embedding_model == "text-embedding-3-small" else None
    return PGVector(
        embeddings=embeddings,
        connection=settings.database_url,
        collection_name=settings.rag_collection,
        embedding_length=embedding_length,
        use_jsonb=True,
        create_extension=False,
    )


def _build_text_splitter(settings: Settings) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        keep_separator=True,
        length_function=len,
        is_separator_regex=False,
        add_start_index=True,
        strip_whitespace=True,
        separators=[
            "\n\n",
            "\n",
            "다. ",
            "요. ",
            ". ",
            "? ",
            "! ",
            " ",
            "",
        ],
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_term(value)).strip()


def _compact_text(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9가-힣]+", "", _normalize_text(value)).casefold()


def _tokenize(value: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(_normalize_text(value)) if len(token) >= 2}


def _token_variants(token: str) -> set[str]:
    normalized = _normalize_text(token).casefold()
    variants = {_compact_text(normalized)}
    base = normalized
    changed = True
    while changed and base:
        changed = False
        for suffix in KOREAN_TOKEN_SUFFIXES:
            if base.endswith(suffix) and len(base) - len(suffix) >= 2:
                base = base[: -len(suffix)]
                compact = _compact_text(base)
                if compact:
                    variants.add(compact)
                changed = True
                break
    compact_normalized = _compact_text(normalized)
    if compact_normalized:
        variants.add(compact_normalized)
    return {variant for variant in variants if variant}


def _extract_tokens(value: str, *, stopwords: set[str]) -> set[str]:
    normalized_stopwords = {_compact_text(word) for word in stopwords} | {word.casefold() for word in stopwords}
    tokens: set[str] = set()
    for token in _tokenize(value):
        variants = _token_variants(token)
        if not variants or variants & normalized_stopwords:
            continue
        tokens.add(_normalize_text(token).casefold())
        tokens.update(variants)
    return {token for token in tokens if token and token not in normalized_stopwords}


def _unsupported_tokens(value: str, context_compact: str, *, stopwords: set[str]) -> list[str]:
    normalized_stopwords = {_compact_text(word) for word in stopwords} | {word.casefold() for word in stopwords}
    unsupported: list[str] = []
    for token in sorted(_tokenize(value)):
        variants = _token_variants(token)
        if not variants or variants & normalized_stopwords:
            continue
        if any(variant in context_compact for variant in variants):
            continue
        unsupported.append(_normalize_text(token))
    return unsupported


def _unsupported_external_terms(value: str, context_compact: str) -> list[str]:
    unsupported: list[str] = []
    for token in sorted(_tokenize(value)):
        if not re.search(r"[A-Za-z0-9]", token):
            continue
        variants = _token_variants(token)
        if any(variant in context_compact for variant in variants):
            continue
        unsupported.append(_normalize_text(token))
    return unsupported


def _contains_unrelated_keyword(value: str) -> bool:
    compact = _compact_text(value)
    return any(keyword in compact for keyword in UNRELATED_KEYWORDS)


def _find_absence_pattern(value: str, *, retrieved_text: str) -> str | None:
    compact_value = _compact_text(value)
    if not compact_value:
        return None
    negation_supported = any(
        _compact_text(marker) in _compact_text(retrieved_text)
        for marker in NEGATION_EVIDENCE_MARKERS
    )
    for pattern in ABSENCE_PATTERNS:
        if _compact_text(pattern) in compact_value:
            if negation_supported:
                return None
            return pattern
    return None


def _split_snippets(documents: list[Document]) -> list[str]:
    snippets: list[str] = []
    for document in documents:
        normalized_text = _normalize_text(document.page_content)
        for part in SNIPPET_SPLIT_RE.split(normalized_text):
            snippet = part.strip(" `\'.,:;\"")
            if len(snippet) < 18:
                continue
            if snippet not in snippets:
                snippets.append(snippet)
    return snippets


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _copy_overlap_ratio(value: str, source: str) -> float:
    compact_value = _compact_text(value)
    compact_source = _compact_text(source)
    if not compact_value or not compact_source:
        return 0.0
    if compact_value in compact_source:
        return 1.0
    match = SequenceMatcher(a=compact_value, b=compact_source).find_longest_match(
        0,
        len(compact_value),
        0,
        len(compact_source),
    )
    return match.size / max(1, len(compact_value))


def _raw_copy_issue(value: str, documents: list[Document], *, kind: str) -> str | None:
    min_chars, threshold = RAW_COPY_LIMITS[kind]
    normalized = _normalize_text(value)
    if len(normalized) < min_chars:
        return None
    best = max((_copy_overlap_ratio(normalized, document.page_content) for document in documents), default=0.0)
    if best >= threshold:
        return f"raw-copy {kind}: ratio={best:.2f}"
    return None


def _derive_focus_terms(claim_text: str, concept_tags: list[str], axis: TopicAxis) -> list[str]:
    focus_terms: list[str] = []
    claim_compact = _compact_text(claim_text)
    for term in concept_tags + [axis.label, *axis.supporting_terms]:
        normalized_term = _normalize_text(term)
        if not normalized_term:
            continue
        if _compact_text(normalized_term) in claim_compact and normalized_term not in focus_terms:
            focus_terms.append(normalized_term)
    if focus_terms:
        return focus_terms[:2]
    candidates = sorted(
        [token for token in _tokenize(claim_text) if token not in GROUNDING_STOPWORDS],
        key=lambda token: (-len(token), token),
    )
    return candidates[:2] or [axis.label]


def _extract_question_focus_terms(question: str) -> list[str]:
    terms = [_normalize_text(match.group(1)) for match in BACKTICK_RE.finditer(question)]
    terms = [term for term in terms if term]
    if terms:
        return _dedupe_preserve_order(terms)[:2]
    normalized_stopwords = {_compact_text(word) for word in QUESTION_FOCUS_STOPWORDS}
    candidates = sorted(
        [
            token
            for token in _tokenize(question)
            if _compact_text(token) not in normalized_stopwords
        ],
        key=lambda token: (-len(token), token),
    )
    return candidates[:2]


def _anchor_question_focus_terms(question: str, candidate: ClaimCandidate) -> list[str]:
    question_compact = _compact_text(question)
    anchored: list[str] = []
    for term in [
        *candidate.focus_terms,
        *candidate.concept_tags,
        candidate.axis.label,
        *candidate.axis.supporting_terms,
    ]:
        normalized = _normalize_text(term)
        compact = _compact_text(normalized)
        if not compact or compact not in question_compact:
            continue
        if normalized not in anchored:
            anchored.append(normalized)
    return anchored[:2]


def _normalize_question_stem(question: str) -> str:
    normalized_stopwords = {_compact_text(word) for word in GROUNDING_STOPWORDS}
    question = re.sub(r"`[^`]+`", "TERM_TOKEN", _normalize_text(question))

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token == "TERM_TOKEN":
            return "<TERM>"
        if _compact_text(token) in normalized_stopwords:
            return token
        return "<TERM>"

    question = re.sub(r"[A-Za-z0-9가-힣_]+", _replace, question)
    question = re.sub(r"\s+", " ", question).strip()
    return question


def _ensure_sentence(text: str) -> str:
    normalized = _normalize_text(text).strip(" .")
    if not normalized:
        return ""
    return normalized + "."


def _claim_kind(claim_text: str) -> str:
    compact = _compact_text(claim_text)
    if any(keyword in compact for keyword in ("차이", "구분", "비교", "구별")):
        return "comparison"
    if any(keyword in compact for keyword in ("조건", "규칙", "경우", "때", "순서")):
        return "condition"
    if any(keyword in compact for keyword in ("용도", "사용", "활용", "통신", "처리")):
        return "application"
    if any(keyword in compact for keyword in ("관계", "연결", "함께", "결합")):
        return "relationship"
    return "definition"


def _preferred_stem_styles(claim_text: str, question_profile: str) -> list[str]:
    primary = _claim_kind(claim_text)
    ordered = [primary]
    if question_profile == "review_5":
        ordered.extend(["relationship", "application", "definition", "condition", "comparison"])
    elif question_profile == "retest_5":
        ordered.extend(["comparison", "condition", "definition", "relationship", "application"])
    else:
        ordered.extend(["definition", "application", "relationship", "condition", "comparison"])
    return _dedupe_preserve_order(ordered)


def _choose_stem_style(claim_text: str, question_profile: str, used_styles: set[str]) -> str:
    for style in _preferred_stem_styles(claim_text, question_profile):
        if style not in used_styles:
            return style
    return _preferred_stem_styles(claim_text, question_profile)[0]


def _select_evidence_chunk_ids(claim_text: str, documents: list[Document]) -> list[str]:
    claim_tokens = _extract_tokens(claim_text, stopwords=GROUNDING_STOPWORDS)
    if not claim_tokens:
        return [str(documents[0].metadata["chunk_id"])] if documents else []
    scored: list[tuple[int, int, str]] = []
    for document in documents:
        chunk_id = str(document.metadata["chunk_id"])
        chunk_compact = _compact_text(document.page_content)
        overlap = sum(1 for token in claim_tokens if _compact_text(token) in chunk_compact)
        scored.append((overlap, -int(document.metadata.get("chunk_order", 0)), chunk_id))
    scored.sort(reverse=True)
    selected = [chunk_id for overlap, _neg_order, chunk_id in scored if overlap > 0][:2]
    if selected:
        return selected
    return [str(documents[0].metadata["chunk_id"])] if documents else []


def _normalize_concept_tags(claim_text: str, concept_tags: list[str], axis: TopicAxis) -> list[str]:
    claim_compact = _compact_text(claim_text)
    tags: list[str] = []
    for tag in concept_tags + [axis.label, *axis.supporting_terms]:
        normalized_tag = _normalize_text(tag)
        if not normalized_tag:
            continue
        if _compact_text(normalized_tag) in claim_compact and normalized_tag not in tags:
            tags.append(normalized_tag)
    if tags:
        return tags[:3]
    candidates = sorted(
        [token for token in _tokenize(claim_text) if token not in GROUNDING_STOPWORDS],
        key=lambda token: (-len(token), token),
    )
    return candidates[:3] or [axis.label]


def _build_learning_goal(question: str, claim_text: str, concept_tags: list[str], topic_axis_label: str) -> str:
    focus_terms = _extract_question_focus_terms(question) or _derive_focus_terms(claim_text, concept_tags, TopicAxis(
        label=topic_axis_label,
        supporting_terms=concept_tags,
        evidence_chunk_ids=[],
        source_corpus_ids=[],
    ))
    focus_phrase = " 및 ".join(focus_terms[:2]) if focus_terms else topic_axis_label
    kind = _claim_kind(claim_text)
    if kind == "comparison":
        return f"{focus_phrase}의 차이를 구분할 수 있다."
    if kind == "condition":
        return f"{focus_phrase}의 조건이나 규칙을 설명할 수 있다."
    if kind == "application":
        return f"{focus_phrase}의 활용 맥락을 설명할 수 있다."
    if kind == "relationship":
        return f"{focus_phrase}의 관계를 설명할 수 있다."
    return f"{focus_phrase}의 특징을 설명할 수 있다."


def _validate_learning_goal_text(learning_goal: str, claim_text: str, question: str) -> list[str]:
    issues: list[str] = []
    normalized_goal = _normalize_text(learning_goal).strip().rstrip(".")
    if "/" in learning_goal:
        issues.append(f"invalid learning_goal slash: {learning_goal}")
    if _contains_unrelated_keyword(learning_goal):
        issues.append(f"unrelated learning_goal: {learning_goal}")
    if any(pattern in normalized_goal for pattern in GENERIC_LEARNING_GOAL_PATTERNS):
        issues.append(f"generic learning_goal: {learning_goal}")
    if not any(normalized_goal.endswith(ending) for ending in ALLOWED_LEARNING_GOAL_ENDINGS):
        issues.append(f"invalid learning_goal ending: {learning_goal}")
    if re.search(r"[A-Za-z0-9+#._-]+와\b", normalized_goal):
        issues.append(f"invalid learning_goal particle: {learning_goal}")
    focus_terms = _extract_question_focus_terms(question) or _derive_focus_terms(
        claim_text,
        [],
        TopicAxis(label="", supporting_terms=[], evidence_chunk_ids=[], source_corpus_ids=[]),
    )
    goal_compact = _compact_text(learning_goal)
    if focus_terms and not any(_compact_text(term) in goal_compact for term in focus_terms):
        issues.append(f"learning_goal mismatch: {learning_goal}")
    return issues


def _issue_code(issue: str) -> str:
    if issue.startswith("raw-copy"):
        return "raw_copy_reject"
    if issue.startswith("question-focus"):
        return "question_focus_mismatch"
    if issue.startswith("learning_goal") or issue.startswith("generic learning_goal") or issue.startswith("invalid learning_goal"):
        return "learning_goal_mismatch"
    if issue.startswith("duplicate stem"):
        return "duplicate_stem"
    return "validation_issue"


def _fit_explanation(text: str, *, max_chars: int = 220) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|(?<=다\.)\s+|(?<=요\.)\s+", normalized) if part.strip()]
    compact = ""
    for part in parts:
        candidate = f"{compact} {part}".strip() if compact else part
        if len(candidate) > max_chars:
            break
        compact = candidate
    if compact:
        return compact
    return normalized[:max_chars].rstrip() + ("." if not normalized[:max_chars].rstrip().endswith(".") else "")


def _align_answer(options: list[str], answer_index: int, answer_text: str) -> tuple[int, str]:
    normalized_answer = _normalize_text(answer_text)
    if normalized_answer in options:
        matched_index = options.index(normalized_answer)
        return matched_index, options[matched_index]
    if 0 <= answer_index < len(options):
        return answer_index, options[answer_index]
    return answer_index, normalized_answer


@dataclass(slots=True)
class LangChainWeeklyQuizGenerator:
    settings: Settings
    repository: Repository
    embeddings: OpenAIEmbeddings
    vector_store: PGVector
    llm: ChatGoogleGenerativeAI
    text_splitter: RecursiveCharacterTextSplitter
    indexed_chunk_ids_by_corpus: dict[str, list[str]] = field(default_factory=dict)
    validation_counters: Counter[str] = field(default_factory=Counter)

    def _emit_progress(self, progress_callback: Callable[[str], None] | None, message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    @classmethod
    def build(cls, settings: Settings, repository: Repository) -> "LangChainWeeklyQuizGenerator":
        embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model)
        vector_store = _build_vector_store(settings, embeddings)
        if settings.rag_llm_provider.lower() != "google":
            raise ValueError(f"Unsupported rag_llm_provider: {settings.rag_llm_provider}")
        llm = ChatGoogleGenerativeAI(model=settings.rag_llm_model, temperature=0.1)
        return cls(
            settings=settings,
            repository=repository,
            embeddings=embeddings,
            vector_store=vector_store,
            llm=llm,
            text_splitter=_build_text_splitter(settings),
        )

    def _planned_documents(self, week: WeeklySelection, corpus: CorpusSelection) -> tuple[list[Document], list[str]]:
        documents: list[Document] = []
        ids: list[str] = []
        if not corpus.cleaned_text.strip():
            return documents, ids
        split_documents = self.text_splitter.create_documents([corpus.cleaned_text])
        for chunk_order, split_document in enumerate(split_documents):
            page_content = _normalize_text(split_document.page_content)
            if not page_content:
                continue
            start_index = int(split_document.metadata.get("start_index", 0))
            chunk_hash = hashlib.sha1(f"{corpus.corpus_id}:{start_index}:{page_content}".encode("utf-8")).hexdigest()[:10]
            chunk_id = f"{corpus.corpus_id}-rag-{chunk_order:03d}-{chunk_hash}"
            source_span = f"char:{start_index}:{start_index + len(split_document.page_content)}"
            documents.append(
                Document(
                    page_content=page_content,
                    metadata={
                        "week_id": week.week_id,
                        "corpus_id": corpus.corpus_id,
                        "source_date": corpus.date,
                        "chunk_id": chunk_id,
                        "chunk_order": chunk_order,
                        "source_span": source_span,
                    },
                )
            )
            ids.append(chunk_id)
        return documents, ids

    def _existing_chunk_ids(self, corpus_id: str) -> list[str]:
        with self.repository.session_factory() as db:
            rows = db.execute(
                sql_text(
                    """
                    select e.id
                    from langchain_pg_embedding as e
                    join langchain_pg_collection as c on c.uuid = e.collection_id
                    where c.name = :collection_name
                      and e.cmetadata->>'corpus_id' = :corpus_id
                    order by e.id
                    """
                ),
                {"collection_name": self.settings.rag_collection, "corpus_id": corpus_id},
            ).scalars()
            return [str(row) for row in rows]

    @traceable(run_type="chain", name="weekly_quiz_rag_index_corpus")
    def index_corpus(self, week: WeeklySelection, corpus: CorpusSelection) -> list[str]:
        documents, ids = self._planned_documents(week, corpus)
        existing_ids = self._existing_chunk_ids(corpus.corpus_id)
        if ids and existing_ids == ids:
            self.indexed_chunk_ids_by_corpus[corpus.corpus_id] = ids
            return ids
        if existing_ids:
            try:
                self.vector_store.delete(ids=existing_ids)
            except Exception:
                pass
        if ids:
            self.vector_store.add_documents(documents, ids=ids)
        self.indexed_chunk_ids_by_corpus[corpus.corpus_id] = ids
        return ids

    @traceable(run_type="chain", name="weekly_quiz_rag_index_week")
    def index_week(self, week: WeeklySelection) -> None:
        for corpus_id in week.corpus_ids:
            corpus = self.repository.get_corpus(corpus_id)
            self.index_corpus(week, corpus)

    def _claim_chain(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "역할: 너는 강의 STT에서 퀴즈 근거가 될 핵심 사실(claim)만 추출하는 분석기다. "
                    "retrieved chunks를 읽고 퀴즈 근거로 쓸 수 있는 claim 1~3개만 추출하라. "
                    "claim은 한국어 한 문장, 20~90자여야 하며 원문을 길게 복사하지 말라. "
                    "positive evidence가 직접 있는 사실만 추출하고, 잡담/운영 멘트/감탄사는 제외하라. "
                    "absence 기반 claim과 chunk 밖의 사실 추가는 금지다."
                ),
                (
                    "human",
                    "source_corpus_id={source_corpus_id}\n"
                    "source_date={source_date}\n"
                    "topic_axis_label={topic_axis_label}\n"
                    "supporting_terms={supporting_terms}\n"
                    "retrieved_chunk_ids={retrieved_chunk_ids}\n\n"
                    "retrieved_chunks=\n{retrieved_chunks}"
                ),
            ]
        )
        return prompt | self.llm.with_structured_output(ClaimBatch)

    def _item_chain(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "역할: 너는 retrieved claim만 근거로 객관식 문항 1개를 만드는 퀴즈 생성기다. "
                    "문제, 보기, 정답, 해설은 claim과 retrieved evidence 안에서만 만들어야 한다. "
                    "문제는 한 문장, 보기는 각각 한 문장 20~80자, 해설은 80~220자 2~3문장으로 작성하라. "
                    "정답은 claim과 직접 일치해야 하며, 오답은 retrieved context 안에서 반박 가능해야 한다. "
                    "retrieved chunks에 없는 새로운 기술명, 버전명, 제품명, 외부 개념은 넣지 마라. "
                    "retrieved evidence가 한국어 용어를 쓰면 같은 의미를 영어 기술명으로 임의 치환하지 말고, "
                    "가능한 한 evidence에 나온 표현 계열을 유지하라. "
                    "문제/보기/정답/해설에 raw chunk를 길게 복사하지 마라. "
                    "absence 기반 설명은 금지다. learning_goal은 질문이 실제로 평가하는 능력을 한국어 1문장으로 작성하라."
                ),
                (
                    "human",
                    "source_corpus_id={source_corpus_id}\n"
                    "source_date={source_date}\n"
                    "topic_axis_label={topic_axis_label}\n"
                    "question_profile={question_profile}\n"
                    "choice_count={choice_count}\n"
                    "stem_style={stem_style}\n"
                    "stem_style_guidance={stem_style_guidance}\n"
                    "claim_text={claim_text}\n"
                    "concept_tags={concept_tags}\n"
                    "focus_terms={focus_terms}\n"
                    "validation_errors={validation_errors}\n\n"
                    "retrieved_chunks=\n{retrieved_chunks}"
                ),
            ]
        )
        return prompt | self.llm.with_structured_output(QuizItemDraft)

    def _build_query(self, axis: TopicAxis, question_profile: str, slot_index: int) -> str:
        supporting_terms = axis.supporting_terms or [axis.label]
        start = slot_index % max(1, len(supporting_terms))
        rotated = supporting_terms[start:] + supporting_terms[:start]
        query_parts = [axis.label, *rotated[:3], PROFILE_HINTS[question_profile]]
        return " ".join(part for part in query_parts if _normalize_text(part))

    @traceable(run_type="retriever", name="weekly_quiz_rag_retrieve")
    def retrieve_documents(
        self,
        *,
        corpus_id: str,
        axis: TopicAxis,
        question_profile: str,
        slot_index: int,
        chunk_usage: Counter[str],
        tuple_usage: Counter[str],
    ) -> list[Document]:
        query = self._build_query(axis, question_profile, slot_index)
        hits = self.vector_store.similarity_search_with_score(
            query,
            k=self.settings.rag_retriever_top_k,
            filter={"corpus_id": corpus_id},
        )
        documents = [document for document, _score in hits]
        if not documents:
            raise ValueError(f"No retrieved documents for corpus_id={corpus_id}, axis={axis.label}")
        return _select_best_documents(
            documents,
            generation_top_k=self.settings.rag_generation_top_k,
            chunk_usage=chunk_usage,
            tuple_usage=tuple_usage,
        )

    @traceable(run_type="chain", name="weekly_quiz_rag_extract_claims")
    def extract_claims(
        self,
        *,
        corpus_id: str,
        source_date: str,
        axis: TopicAxis,
        documents: list[Document],
    ) -> list[ClaimRecord]:
        retrieved_chunks = "\n\n".join(
            f"[{document.metadata['chunk_id']}] {document.page_content}" for document in documents
        )
        retrieved_chunk_ids = [str(document.metadata["chunk_id"]) for document in documents]
        retrieved_text = " ".join(document.page_content for document in documents)
        valid_records: list[ClaimRecord] = []
        for _attempt in range(2):
            draft = self._claim_chain().invoke(
                {
                    "source_corpus_id": corpus_id,
                    "source_date": source_date,
                    "topic_axis_label": axis.label,
                    "supporting_terms": ", ".join(axis.supporting_terms),
                    "retrieved_chunk_ids": ", ".join(retrieved_chunk_ids),
                    "retrieved_chunks": retrieved_chunks,
                }
            )
            seen: set[str] = set()
            valid_records = []
            for record in draft.claims:
                claim_text = _ensure_sentence(record.claim_text)
                if not claim_text or len(claim_text) < 20 or len(claim_text) > 90:
                    continue
                if _find_absence_pattern(claim_text, retrieved_text=retrieved_text):
                    continue
                if _raw_copy_issue(claim_text, documents, kind="claim"):
                    continue
                evidence_chunk_ids = [chunk_id for chunk_id in record.evidence_chunk_ids if chunk_id in retrieved_chunk_ids]
                if not evidence_chunk_ids:
                    evidence_chunk_ids = _select_evidence_chunk_ids(claim_text, documents)
                concept_tags = _normalize_concept_tags(claim_text, record.concept_tags, axis)
                claim_key = _compact_text(claim_text)
                if claim_key in seen:
                    continue
                seen.add(claim_key)
                valid_records.append(
                    ClaimRecord(
                        claim_text=claim_text,
                        concept_tags=concept_tags,
                        evidence_chunk_ids=evidence_chunk_ids,
                    )
                )
            if valid_records:
                return valid_records
        raise ValueError(f"No valid claims extracted for corpus_id={corpus_id}, axis={axis.label}")

    def _build_candidate_pool(
        self,
        *,
        corpus: CorpusSelection,
        axes: list[TopicAxis],
        num_questions: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[ClaimCandidate]:
        pool: list[ClaimCandidate] = []
        chunk_usage: Counter[str] = Counter()
        tuple_usage: Counter[str] = Counter()
        seen_pairs: set[tuple[str, str]] = set()
        seen_claim_keys: set[str] = set()
        rounds = max(num_questions, len(axes) * 2)
        target_unique_claims = num_questions + min(2, max(1, len(axes)))
        for slot_index in range(rounds):
            question_profile = PROFILE_SEQUENCE[slot_index % len(PROFILE_SEQUENCE)]
            choice_count = PROFILE_CHOICE_COUNT[question_profile]
            axis = axes[slot_index % len(axes)]
            self._emit_progress(
                progress_callback,
                f"quiz corpus retrieval start corpus_id={corpus.corpus_id} slot={slot_index + 1}/{rounds} axis={axis.label} profile={question_profile}",
            )
            documents = self.retrieve_documents(
                corpus_id=corpus.corpus_id,
                axis=axis,
                question_profile=question_profile,
                slot_index=slot_index,
                chunk_usage=chunk_usage,
                tuple_usage=tuple_usage,
            )
            retrieved_chunk_ids = [str(document.metadata["chunk_id"]) for document in documents]
            tuple_key = "|".join(retrieved_chunk_ids)
            tuple_usage[tuple_key] += 1
            for chunk_id in retrieved_chunk_ids:
                chunk_usage[chunk_id] += 1
            claims = self.extract_claims(
                corpus_id=corpus.corpus_id,
                source_date=corpus.date,
                axis=axis,
                documents=documents,
            )
            self._emit_progress(
                progress_callback,
                f"quiz corpus claims done corpus_id={corpus.corpus_id} slot={slot_index + 1}/{rounds} claims={len(claims)} retrieved={len(retrieved_chunk_ids)}",
            )
            for claim in claims:
                focus_terms = _derive_focus_terms(claim.claim_text, claim.concept_tags, axis)
                candidate = ClaimCandidate(
                    corpus_id=corpus.corpus_id,
                    source_date=corpus.date,
                    axis=axis,
                    question_profile=question_profile,
                    choice_count=choice_count,
                    documents=documents,
                    retrieved_chunk_ids=retrieved_chunk_ids,
                    claim_text=claim.claim_text,
                    concept_tags=claim.concept_tags,
                    evidence_chunk_ids=claim.evidence_chunk_ids,
                    focus_terms=focus_terms,
                    primary_focus=focus_terms[0] if focus_terms else axis.label,
                    tuple_key=tuple_key,
                    claim_key=_compact_text(claim.claim_text),
                    slot_index=slot_index,
                )
                pair_key = (candidate.claim_key, candidate.tuple_key)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                seen_claim_keys.add(candidate.claim_key)
                pool.append(candidate)
            if len(seen_claim_keys) >= target_unique_claims and len(pool) >= num_questions:
                self._emit_progress(
                    progress_callback,
                    f"quiz corpus candidate pool early-stop corpus_id={corpus.corpus_id} slot={slot_index + 1}/{rounds} unique_claims={len(seen_claim_keys)} pool={len(pool)}",
                )
                break
        return pool

    @traceable(run_type="chain", name="weekly_quiz_rag_plan_corpus")
    def plan_corpus_questions(
        self,
        *,
        corpus: CorpusSelection,
        axes: list[TopicAxis],
        num_questions: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[ClaimCandidate]:
        pool = self._build_candidate_pool(
            corpus=corpus,
            axes=axes,
            num_questions=num_questions,
            progress_callback=progress_callback,
        )
        if len({candidate.claim_key for candidate in pool}) < num_questions:
            raise ValueError(f"Not enough unique claims for corpus_id={corpus.corpus_id}")
        selected: list[ClaimCandidate] = []
        used_claims: set[str] = set()
        used_styles: set[str] = set()
        focus_usage: Counter[str] = Counter()
        tuple_usage: Counter[str] = Counter()
        used_tags: set[str] = set()
        desired_profiles = [PROFILE_SEQUENCE[index % len(PROFILE_SEQUENCE)] for index in range(num_questions)]
        for slot_index, desired_profile in enumerate(desired_profiles):
            remaining = [candidate for candidate in pool if candidate.claim_key not in used_claims]
            if not remaining:
                break
            ranked = sorted(
                remaining,
                key=lambda candidate: (
                    focus_usage[candidate.primary_focus],
                    tuple_usage[candidate.tuple_key],
                    candidate.question_profile != desired_profile,
                    len(set(_compact_text(tag) for tag in candidate.concept_tags) & used_tags),
                    abs(len(candidate.claim_text) - 48),
                    candidate.slot_index,
                ),
            )
            chosen = ranked[0]
            chosen.stem_style = _choose_stem_style(chosen.claim_text, chosen.question_profile, used_styles)
            selected.append(chosen)
            used_claims.add(chosen.claim_key)
            used_styles.add(chosen.stem_style)
            focus_usage[chosen.primary_focus] += 1
            tuple_usage[chosen.tuple_key] += 1
            used_tags.update(_compact_text(tag) for tag in chosen.concept_tags)
        if len(selected) < num_questions:
            raise ValueError(f"Failed to plan {num_questions} unique claims for corpus_id={corpus.corpus_id}")
        self._emit_progress(
            progress_callback,
            f"quiz corpus selection done corpus_id={corpus.corpus_id} selected={len(selected)} pool={len(pool)}",
        )
        return selected

    @traceable(run_type="chain", name="weekly_quiz_rag_generate_item_draft")
    def generate_item_draft(self, candidate: ClaimCandidate, validation_errors: list[str] | None = None) -> QuizItemDraft:
        retrieved_chunks = "\n\n".join(
            f"[{document.metadata['chunk_id']}] {document.page_content}" for document in candidate.documents
        )
        return self._item_chain().invoke(
            {
                "source_corpus_id": candidate.corpus_id,
                "source_date": candidate.source_date,
                "topic_axis_label": candidate.axis.label,
                "question_profile": candidate.question_profile,
                "choice_count": candidate.choice_count,
                "stem_style": candidate.stem_style,
                "stem_style_guidance": QUESTION_STEM_GUIDANCE[candidate.stem_style],
                "claim_text": candidate.claim_text,
                "concept_tags": ", ".join(candidate.concept_tags),
                "focus_terms": ", ".join(candidate.focus_terms),
                "validation_errors": " | ".join(validation_errors or []) or "없음",
                "retrieved_chunks": retrieved_chunks,
            }
        )

    def _record_issues(self, issues: list[str]) -> None:
        for issue in issues:
            self.validation_counters[_issue_code(issue)] += 1

    def _validate_item(self, item: WeeklyQuizItem, candidate: ClaimCandidate) -> list[str]:
        issues: list[str] = []
        retrieved_text = " ".join(document.page_content for document in candidate.documents)
        context_compact = _compact_text(" ".join([
            candidate.claim_text,
            candidate.axis.label,
            *candidate.axis.supporting_terms,
            *candidate.concept_tags,
            retrieved_text,
        ]))

        if len(item.options) != item.choice_count:
            issues.append("format options length mismatch")
        if any(len(option) < 20 or len(option) > 80 for option in item.options):
            issues.append("format option length out of range")
        if len(item.explanation) < 80 or len(item.explanation) > 220:
            issues.append("format explanation length out of range")
        if len(set(item.options)) != len(item.options):
            issues.append("format duplicate options")
        option_lengths = [len(option) for option in item.options]
        if option_lengths and max(option_lengths) > min(option_lengths) * 2:
            issues.append("format option length imbalance")
        for option in item.options:
            raw_copy = _raw_copy_issue(option, candidate.documents, kind="option")
            if raw_copy:
                issues.append(raw_copy)
        answer_copy = _raw_copy_issue(item.answer_text, candidate.documents, kind="answer")
        if answer_copy:
            issues.append(answer_copy)
        explanation_copy = _raw_copy_issue(item.explanation, candidate.documents, kind="explanation")
        if explanation_copy:
            issues.append(explanation_copy)
        if _find_absence_pattern(item.explanation, retrieved_text=retrieved_text):
            issues.append(f"absence-based explanation: {item.explanation}")
        for option in item.options:
            if _find_absence_pattern(option, retrieved_text=retrieved_text):
                issues.append(f"absence-based option: {option}")

        question_focus_terms = _anchor_question_focus_terms(item.question, candidate) or _extract_question_focus_terms(item.question)
        claim_focus_terms = candidate.focus_terms or _derive_focus_terms(candidate.claim_text, candidate.concept_tags, candidate.axis)
        claim_context = " ".join(
            [
                candidate.claim_text,
                candidate.axis.label,
                *candidate.axis.supporting_terms,
                *candidate.concept_tags,
                *claim_focus_terms,
            ]
        )
        claim_context_compact = _compact_text(claim_context)
        claim_context_tokens = {_compact_text(token) for token in _tokenize(claim_context)}
        question_focus_compacts = {_compact_text(term) for term in question_focus_terms}
        if question_focus_compacts and not (
            (question_focus_compacts & claim_context_tokens)
            or any(term in claim_context_compact for term in question_focus_compacts)
        ):
            issues.append(f"question-focus mismatch: question={item.question} claim={candidate.claim_text}")
        answer_tokens = _extract_tokens(item.answer_text, stopwords=GROUNDING_STOPWORDS)
        if answer_tokens and not any(
            (_compact_text(token) in claim_context_compact) or (_compact_text(token) in claim_context_tokens)
            for token in answer_tokens
        ):
            issues.append(f"question-focus mismatch: answer={item.answer_text} claim={candidate.claim_text}")

        for option in item.options:
            if _contains_unrelated_keyword(option):
                issues.append(f"unrelated option keyword: {option}")
            option_unsupported = _unsupported_external_terms(option, context_compact)
            if option_unsupported:
                issues.append(f"ungrounded option tokens: {option_unsupported}")

        correct_option = item.options[item.answer_index] if 0 <= item.answer_index < len(item.options) else ""
        if correct_option.strip() != item.answer_text.strip():
            issues.append("format answer mismatch")
        correct_option_tokens = _extract_tokens(correct_option, stopwords=GROUNDING_STOPWORDS)
        if correct_option_tokens and not any(
            (_compact_text(token) in claim_context_compact) or (_compact_text(token) in claim_context_tokens)
            for token in correct_option_tokens
        ):
            issues.append(f"question-focus mismatch: correct_option={correct_option} claim={candidate.claim_text}")

        issues.extend(_validate_learning_goal_text(item.learning_goal, candidate.claim_text, item.question))
        return issues

    def _build_item(self, candidate: ClaimCandidate) -> WeeklyQuizItem:
        validation_errors: list[str] = []
        last_issues: list[str] = []
        for _attempt in range(2):
            draft = self.generate_item_draft(candidate, validation_errors=validation_errors)
            question = _normalize_text(draft.question)
            options = [_normalize_text(option) for option in draft.options]
            explanation = _fit_explanation(draft.explanation)
            learning_goal = _normalize_text(draft.learning_goal)
            fallback_learning_goal = _build_learning_goal(
                question=question,
                claim_text=candidate.claim_text,
                concept_tags=candidate.concept_tags,
                topic_axis_label=candidate.axis.label,
            )
            if _validate_learning_goal_text(learning_goal, candidate.claim_text, question):
                learning_goal = fallback_learning_goal
            answer_index, answer_text = _align_answer(options, draft.answer_index, draft.answer_text)
            item = WeeklyQuizItem(
                question_profile=candidate.question_profile,
                choice_count=candidate.choice_count,
                question=question,
                options=options,
                answer_index=answer_index,
                answer_text=answer_text,
                explanation=explanation,
                difficulty={"basic_eval_4": "easy", "review_5": "medium", "retest_5": "hard"}[candidate.question_profile],
                evidence_chunk_ids=candidate.evidence_chunk_ids,
                learning_goal=learning_goal,
                topic_axis_label=candidate.axis.label,
                source_corpus_id=candidate.corpus_id,
                source_date=candidate.source_date,
                retrieved_chunk_ids=candidate.retrieved_chunk_ids,
                learning_goal_source="generated",
            )
            last_issues = self._validate_item(item, candidate)
            if not last_issues:
                return item
            self._record_issues(last_issues)
            validation_errors = last_issues
        raise ValueError(
            f"Strict RAG validation failed for corpus_id={candidate.corpus_id}, axis={candidate.axis.label}: {last_issues[:6]}"
        )

    def _collect_corpus_issues(
        self,
        corpus_id: str,
        items: list[WeeklyQuizItem],
        planned_claims: list[ClaimCandidate],
    ) -> list[str]:
        issues: list[str] = []
        if len(items) < 5:
            issues.append(f"{corpus_id} generated fewer than 5 items")
        unique_chunks = {chunk_id for item in items for chunk_id in item.retrieved_chunk_ids}
        indexed_chunk_count = len(self.indexed_chunk_ids_by_corpus.get(corpus_id, []))
        required_unique = min(3, indexed_chunk_count) if indexed_chunk_count else 0
        if required_unique and len(unique_chunks) < required_unique:
            issues.append(f"{corpus_id} retrieval diversity too low: unique_chunks={len(unique_chunks)} required={required_unique}")
        tuple_counts = Counter(tuple(item.retrieved_chunk_ids) for item in items)
        for chunk_tuple, count in tuple_counts.items():
            if count > 2:
                issues.append(f"{corpus_id} repeated retrieved tuple more than twice: {list(chunk_tuple)} x {count}")
        stem_counts = Counter(_normalize_question_stem(item.question) for item in items)
        for stem, count in stem_counts.items():
            if count > 1:
                issues.append(f"duplicate stem: {corpus_id} {stem} x {count}")
        claim_counts = Counter(candidate.claim_key for candidate in planned_claims)
        for claim_key, count in claim_counts.items():
            if count > 1:
                issues.append(f"duplicate claim: {corpus_id} {claim_key} x {count}")
        return issues

    @traceable(run_type="chain", name="weekly_quiz_rag_generate_weekly_quiz_set")
    def generate_weekly_quiz_set(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        *,
        num_questions: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> WeeklyQuizSet:
        self._emit_progress(
            progress_callback,
            f"quiz indexing start week_id={week.week_id} corpora={len(week.corpus_ids)} chunking=recursive:{self.settings.rag_chunk_size}/{self.settings.rag_chunk_overlap}",
        )
        self.index_week(week)
        self._emit_progress(progress_callback, f"quiz indexing done week_id={week.week_id}")
        self.validation_counters.clear()
        all_items: list[WeeklyQuizItem] = []
        per_corpus_issues: list[str] = []
        for corpus_id in week.corpus_ids:
            corpus = self.repository.get_corpus(corpus_id)
            axes = [axis for axis in topic_set.topic_axes if corpus_id in axis.source_corpus_ids]
            if not axes:
                raise ValueError(f"No topic axis covers corpus_id={corpus_id}")
            self._emit_progress(
                progress_callback,
                f"quiz corpus start corpus_id={corpus_id} axes={len(axes)} required_items={num_questions}",
            )
            planned_claims: list[ClaimCandidate] | None = None
            planning_error: Exception | None = None
            for planned_count in dict.fromkeys((num_questions + 4, num_questions + 2, num_questions + 1, num_questions)):
                try:
                    self._emit_progress(
                        progress_callback,
                        f"quiz corpus planning start corpus_id={corpus_id} target={planned_count}",
                    )
                    planned_claims = self.plan_corpus_questions(
                        corpus=corpus,
                        axes=axes,
                        num_questions=planned_count,
                        progress_callback=progress_callback,
                    )
                    self._emit_progress(
                        progress_callback,
                        f"quiz corpus planning done corpus_id={corpus_id} planned_claims={len(planned_claims)}",
                    )
                    break
                except Exception as exc:
                    planning_error = exc
            if planned_claims is None:
                raise ValueError(f"Failed to plan candidates for corpus_id={corpus_id}: {planning_error}")
            corpus_items: list[WeeklyQuizItem] = []
            accepted_candidates: list[ClaimCandidate] = []
            for candidate_index, candidate in enumerate(planned_claims, start=1):
                self._emit_progress(
                    progress_callback,
                    f"quiz corpus item build start corpus_id={corpus_id} candidate={candidate_index}/{len(planned_claims)} profile={candidate.question_profile} focus={candidate.primary_focus}",
                )
                try:
                    item = self._build_item(candidate)
                except ValueError as exc:
                    self.validation_counters["candidate_retry_exhausted"] += 1
                    self._emit_progress(
                        progress_callback,
                        f"quiz corpus item rejected corpus_id={corpus_id} candidate={candidate_index}/{len(planned_claims)} "
                        f"reason={str(exc)[:220]}",
                    )
                    continue
                corpus_items.append(item)
                accepted_candidates.append(candidate)
                self._emit_progress(
                    progress_callback,
                    f"quiz corpus item accepted corpus_id={corpus_id} accepted={len(corpus_items)}/{num_questions}",
                )
                if len(corpus_items) >= num_questions:
                    break
            if len(corpus_items) < num_questions:
                self._emit_progress(
                    progress_callback,
                    f"quiz corpus failed corpus_id={corpus_id} required={num_questions} generated={len(corpus_items)} "
                    f"validation_counters={dict(self.validation_counters)}",
                )
                raise ValueError(
                    f"Strict weekly quiz generation could not fill corpus_id={corpus_id}: "
                    f"required={num_questions} generated={len(corpus_items)}"
                )
            per_corpus_issues.extend(self._collect_corpus_issues(corpus_id, corpus_items, accepted_candidates))
            all_items.extend(corpus_items)
            unique_chunks = len({chunk_id for item in corpus_items for chunk_id in item.retrieved_chunk_ids})
            self._emit_progress(
                progress_callback,
                f"quiz corpus done corpus_id={corpus_id} items={len(corpus_items)} unique_retrieved_chunks={unique_chunks}",
            )
        if per_corpus_issues:
            self._record_issues(per_corpus_issues)
            raise ValueError(f"Strict weekly quiz validation failed: {per_corpus_issues[:8]}")
        self._emit_progress(
            progress_callback,
            f"quiz weekly done week_id={week.week_id} total_items={len(all_items)} validation_counters={dict(self.validation_counters)}",
        )
        return WeeklyQuizSet(
            week_id=week.week_id,
            mode="weekly",
            topic_axes=topic_set.topic_axes,
            items=all_items,
            corpus_ids=week.corpus_ids,
            min_questions_per_corpus=num_questions,
            model_info={
                "backend": f"langchain:{self.settings.rag_llm_model}",
                "collection": self.settings.rag_collection,
                "chunking": f"recursive:{self.settings.rag_chunk_size}/{self.settings.rag_chunk_overlap}",
                "retriever_top_k": str(self.settings.rag_retriever_top_k),
                "generation_top_k": str(self.settings.rag_generation_top_k),
                "strict_rag": "true",
                "tracing": os.getenv("LANGSMITH_TRACING", "false"),
            },
        )


def _select_best_documents(
    documents: list[Document],
    *,
    generation_top_k: int,
    chunk_usage: Counter[str],
    tuple_usage: Counter[str],
) -> list[Document]:
    unique_docs: list[Document] = []
    seen: set[str] = set()
    for document in documents:
        chunk_id = str(document.metadata["chunk_id"])
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        unique_docs.append(document)
    if len(unique_docs) <= generation_top_k:
        return unique_docs
    combos = list(combinations(unique_docs[: min(len(unique_docs), 6)], generation_top_k))
    best_combo = min(
        combos,
        key=lambda combo: (
            tuple_usage.get("|".join(str(doc.metadata["chunk_id"]) for doc in combo), 0) >= 2,
            tuple_usage.get("|".join(str(doc.metadata["chunk_id"]) for doc in combo), 0),
            -sum(1 for doc in combo if chunk_usage.get(str(doc.metadata["chunk_id"]), 0) == 0),
            sum(chunk_usage.get(str(doc.metadata["chunk_id"]), 0) for doc in combo),
            sum(int(doc.metadata.get("chunk_order", 0)) for doc in combo),
        ),
    )
    return list(best_combo)
