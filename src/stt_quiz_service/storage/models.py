from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LectureRecord(Base):
    __tablename__ = "lectures"

    lecture_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    corpus_id: Mapped[str] = mapped_column(String(128), index=True)
    week: Mapped[int] = mapped_column(Integer, default=0, index=True)
    date: Mapped[str] = mapped_column(String(32), index=True)
    session: Mapped[str] = mapped_column(String(16), index=True)
    subject: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    learning_goal: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text)
    cleaned_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)


class ChunkRecord(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    corpus_id: Mapped[str] = mapped_column(String(128), index=True)
    lecture_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    session: Mapped[str] = mapped_column(String(16), default="")
    chunk_order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    source_span: Mapped[str] = mapped_column(String(64))
    practice_example: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    embedding: Mapped["EmbeddingRecord"] = relationship(
        back_populates="chunk", cascade="all, delete-orphan", uselist=False
    )


class EmbeddingRecord(Base):
    __tablename__ = "embeddings"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.chunk_id", ondelete="CASCADE"), primary_key=True
    )
    vector: Mapped[list[float]] = mapped_column(Vector().with_variant(JSON, "sqlite"))
    provider: Mapped[str] = mapped_column(String(64))
    dimension: Mapped[int] = mapped_column(Integer)

    chunk: Mapped["ChunkRecord"] = relationship(back_populates="embedding")


class GenerationRunRecord(Base):
    __tablename__ = "generation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    lecture_id: Mapped[str] = mapped_column(String(128), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    retrieval_query: Mapped[str] = mapped_column(Text, default="")
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, default=0)
    embedder_provider: Mapped[str] = mapped_column(String(64), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[str] = mapped_column(String(128), default="")
    evaluation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class QuizSetRecord(Base):
    __tablename__ = "quiz_sets"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    lecture_id: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class StudyGuideRecord(Base):
    __tablename__ = "study_guides"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    lecture_id: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class RetrievalHitRecord(Base):
    __tablename__ = "retrieval_hits"

    hit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("generation_runs.run_id", ondelete="CASCADE"), index=True
    )
    lecture_id: Mapped[str] = mapped_column(String(128), index=True)
    corpus_id: Mapped[str] = mapped_column(String(128), index=True)
    chunk_id: Mapped[str] = mapped_column(String(128), index=True)
    session: Mapped[str] = mapped_column(String(16), default="")
    chunk_order: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    text_snapshot: Mapped[str] = mapped_column(Text)
    source_span: Mapped[str] = mapped_column(String(64))
    practice_example: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    lecture_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DailyTermCandidateRecord(Base):
    __tablename__ = "daily_term_candidates"

    corpus_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    week_id: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class WeeklyTopicSetRecord(Base):
    __tablename__ = "weekly_topic_sets"

    week_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class WeeklyGuideRecord(Base):
    __tablename__ = "weekly_guides"

    week_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class WeeklyQuizSetRecord(Base):
    __tablename__ = "weekly_quiz_sets"

    week_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class WeeklyQuizSubmissionAttemptRecord(Base):
    __tablename__ = "weekly_quiz_submission_attempts"

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    week_id: Mapped[str] = mapped_column(String(32), index=True)
    submitted_at: Mapped[str] = mapped_column(String(64), index=True)
    total_questions: Mapped[int] = mapped_column(Integer)
    correct_count: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)


class WeeklyQuizSubmissionAnswerRecord(Base):
    __tablename__ = "weekly_quiz_submission_answers"

    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("weekly_quiz_submission_attempts.attempt_id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    question_order: Mapped[int] = mapped_column(Integer)
    selected_option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct_option_index: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
