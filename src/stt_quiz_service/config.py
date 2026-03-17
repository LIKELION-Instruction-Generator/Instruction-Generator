from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    database_url: str
    embedding_backend: str = "auto"
    embedding_dim: int = 64
    top_k: int = 6
    exclude_practice_examples: bool = True
    default_model: str = "claude-sonnet-4-20250514"
    preprocess_model: str = "google-gla:gemini-2.5-flash"
    weekly_model: str = "google-gla:gemini-2.5-flash"
    preprocess_block_chars: int = 3000
    keyword_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    daily_term_candidate_limit: int = 40
    openai_embedding_model: str = "text-embedding-3-small"
    rag_llm_provider: str = "google"
    rag_llm_model: str = "gemini-2.5-flash"
    rag_collection: str = "stt_quiz_chunks_v2"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    rag_retriever_top_k: int = 6
    rag_generation_top_k: int = 3
    llm_backend: str = "mock"
    api_url: str = "http://localhost:8000"
    transcripts_root: Path = Path("NLP_Task2/강의 스크립트")
    curriculum_path: Path = Path("NLP_Task2/강의 커리큘럼.csv")


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("STT_QUIZ_DATABASE_URL", "sqlite:///./stt_quiz_service.db"),
        embedding_backend=os.getenv("STT_QUIZ_EMBEDDING_BACKEND", "auto"),
        embedding_dim=int(os.getenv("STT_QUIZ_EMBEDDING_DIM", "64")),
        top_k=int(os.getenv("STT_QUIZ_TOP_K", "6")),
        exclude_practice_examples=_env_bool("STT_QUIZ_EXCLUDE_PRACTICE", True),
        default_model=os.getenv("STT_QUIZ_DEFAULT_MODEL", "claude-sonnet-4-20250514"),
        preprocess_model=os.getenv("STT_QUIZ_PREPROCESS_MODEL", "google-gla:gemini-2.5-flash"),
        weekly_model=os.getenv("STT_QUIZ_WEEKLY_MODEL", "google-gla:gemini-2.5-flash"),
        preprocess_block_chars=int(os.getenv("STT_QUIZ_PREPROCESS_BLOCK_CHARS", "3000")),
        keyword_embedding_model=os.getenv(
            "STT_QUIZ_KEYWORD_EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        daily_term_candidate_limit=int(os.getenv("STT_QUIZ_DAILY_TERM_CANDIDATE_LIMIT", "40")),
        openai_embedding_model=os.getenv(
            "STT_QUIZ_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
        rag_llm_provider=os.getenv("STT_QUIZ_RAG_LLM_PROVIDER", "google"),
        rag_llm_model=os.getenv("STT_QUIZ_RAG_LLM_MODEL", "gemini-2.5-flash"),
        rag_collection=os.getenv("STT_QUIZ_RAG_COLLECTION", "stt_quiz_chunks_v2"),
        rag_chunk_size=int(os.getenv("STT_QUIZ_RAG_CHUNK_SIZE", "800")),
        rag_chunk_overlap=int(os.getenv("STT_QUIZ_RAG_CHUNK_OVERLAP", "100")),
        rag_retriever_top_k=int(os.getenv("STT_QUIZ_RAG_RETRIEVER_TOP_K", "6")),
        rag_generation_top_k=int(os.getenv("STT_QUIZ_RAG_GENERATION_TOP_K", "3")),
        llm_backend=os.getenv("STT_QUIZ_LLM_BACKEND", "mock"),
        api_url=os.getenv("STT_QUIZ_API_URL", "http://localhost:8000"),
        transcripts_root=Path(
            os.getenv("STT_QUIZ_TRANSCRIPTS_ROOT", "NLP_Task2/강의 스크립트")
        ),
        curriculum_path=Path(
            os.getenv("STT_QUIZ_CURRICULUM_PATH", "NLP_Task2/강의 커리큘럼.csv")
        ),
    )
