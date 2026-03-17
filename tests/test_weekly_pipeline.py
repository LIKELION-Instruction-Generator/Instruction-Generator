from __future__ import annotations

from collections import Counter

import pytest

from stt_quiz_service.schemas import (
    DailyTermCandidate,
    DailyTermCandidates,
    PipelineBuildWeeklyTopicsRequest,
    PipelineExtractTermCandidatesRequest,
    PipelineGenerateWeeklyGuidesRequest,
    PipelineGenerateWeeklyQuizzesRequest,
    PipelinePrepareRequest,
)


@pytest.fixture(autouse=True)
def _disable_langchain_weekly_quiz_generator(monkeypatch):
    # Keep weekly pipeline tests focused on orchestrator contracts.
    # LangChain weekly quiz generator requires PostgreSQL JSONB types, which are
    # incompatible with the sqlite test fixture.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _prepare(orchestrator, tmp_path):
    return orchestrator.prepare_corpus(
        PipelinePrepareRequest(
            transcripts_root=str(orchestrator.settings.transcripts_root),
            curriculum_path=str(orchestrator.settings.curriculum_path),
            output_dir=str(tmp_path / "prepared"),
        )
    )


def test_weekly_pipeline_builds_topics_guides_and_quizzes(orchestrator, tmp_path, monkeypatch):
    prepared = _prepare(orchestrator, tmp_path)
    assert prepared.corpus_ids

    def fake_extract(self, *, corpus_id: str, week_id: str, cleaned_text: str, chunks):
        head = corpus_id.split("-")[-1]
        return DailyTermCandidates(
            corpus_id=corpus_id,
            week_id=week_id,
            candidates=[
                DailyTermCandidate(
                    term=f"{head} 핵심 주제",
                    score=0.95,
                    evidence_chunk_ids=[chunk.chunk_id for chunk in chunks[:2]],
                ),
                DailyTermCandidate(
                    term=f"{head} supporting term",
                    score=0.8,
                    evidence_chunk_ids=[chunk.chunk_id for chunk in chunks[1:3]],
                ),
            ],
        )

    monkeypatch.setattr(type(orchestrator.candidate_extractor), "extract", fake_extract)

    extraction = orchestrator.extract_term_candidates(PipelineExtractTermCandidatesRequest())
    assert extraction.extracted_count == len(prepared.corpus_ids)

    weeks = orchestrator.list_weeks()
    assert weeks
    week_id = weeks[0].week_id

    built = orchestrator.build_weekly_topics(PipelineBuildWeeklyTopicsRequest(week_ids=[week_id]))
    assert built.built_count == 1
    topic_set = orchestrator.get_weekly_topics(week_id)
    assert 1 <= len(topic_set.topic_axes) <= 3
    assert all(axis.supporting_terms for axis in topic_set.topic_axes)

    guides = orchestrator.generate_weekly_guides(PipelineGenerateWeeklyGuidesRequest(week_ids=[week_id]))
    assert guides.generated_count == 1
    guide = orchestrator.get_weekly_guide(week_id)
    assert guide.learning_paragraph
    assert guide.topic_axes

    quizzes = orchestrator.generate_weekly_quizzes(
        PipelineGenerateWeeklyQuizzesRequest(week_ids=[week_id], num_questions=5)
    )
    assert quizzes.generated_count == 1
    quiz_set = orchestrator.get_weekly_quiz(week_id)
    expected_count = len(weeks[0].corpus_ids) * 5
    assert len(quiz_set.items) == expected_count
    assert quiz_set.min_questions_per_corpus == 5
    assert sorted(quiz_set.corpus_ids) == sorted(weeks[0].corpus_ids)
    per_corpus_counts = Counter(item.source_corpus_id for item in quiz_set.items)
    assert all(per_corpus_counts.get(corpus_id, 0) == 5 for corpus_id in weeks[0].corpus_ids)
    assert all(item.source_date == item.source_corpus_id for item in quiz_set.items)
    assert all(item.retrieved_chunk_ids for item in quiz_set.items)
    assert all(item.evidence_chunk_ids for item in quiz_set.items)
    assert all(
        all(chunk_id.startswith(f"{item.source_corpus_id}-") for chunk_id in item.retrieved_chunk_ids)
        for item in quiz_set.items
    )
    assert all(
        all(chunk_id.startswith(f"{item.source_corpus_id}-") for chunk_id in item.evidence_chunk_ids)
        for item in quiz_set.items
    )
    axis_sources = {axis.label: set(axis.source_corpus_ids) for axis in topic_set.topic_axes}
    mismatched = [
        item
        for item in quiz_set.items
        if item.source_corpus_id not in axis_sources.get(item.topic_axis_label, set())
    ]
    assert len({item.topic_axis_label for item in quiz_set.items}) >= 1
    report = orchestrator.get_weekly_report(week_id)
    assert report.question_type_metrics
    assert report.topic_coverage
    assert report.mismatched_axis_item_count == len(mismatched)
    assert sum(report.learning_goal_source_distribution.values()) == len(quiz_set.items)


def test_weekly_topic_build_reuses_seeded_candidates_without_upstream_reextract(
    orchestrator, tmp_path, monkeypatch
):
    prepared = _prepare(orchestrator, tmp_path)
    assert prepared.corpus_ids

    weeks = orchestrator.list_weeks()
    assert weeks
    week = weeks[0]

    for corpus_id in week.corpus_ids:
        chunks = orchestrator.repository.get_chunks_for_corpus(corpus_id)
        orchestrator.repository.save_daily_term_candidates(
            DailyTermCandidates(
                corpus_id=corpus_id,
                week_id=week.week_id,
                candidates=[
                    DailyTermCandidate(
                        term=f"{corpus_id} seeded term",
                        score=0.9,
                        evidence_chunk_ids=[chunk.chunk_id for chunk in chunks[:2]],
                    )
                ],
            )
        )

    def _raise_if_called(_self, _request):
        raise AssertionError("extract_term_candidates must not run when all week candidates are pre-seeded")

    monkeypatch.setattr(type(orchestrator), "extract_term_candidates", _raise_if_called)

    topic_set = orchestrator._build_weekly_topic_set(week.week_id)
    assert topic_set.topic_axes
    asserted_corpus_ids = {corpus_id for axis in topic_set.topic_axes for corpus_id in axis.source_corpus_ids}
    assert asserted_corpus_ids
    assert asserted_corpus_ids.issubset(set(week.corpus_ids))
