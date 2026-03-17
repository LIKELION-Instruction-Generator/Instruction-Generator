from __future__ import annotations


from pathlib import Path

from stt_quiz_service.schemas import PipelineIndexRequest, PipelinePrepareRequest


def test_metadata_filter_limits_chunks_to_selected_lecture(orchestrator, tmp_path):
    prepared = orchestrator.prepare_corpus(
        PipelinePrepareRequest(
            transcripts_root=str(orchestrator.settings.transcripts_root),
            curriculum_path=str(orchestrator.settings.curriculum_path),
            output_dir=str(tmp_path / "prepared"),
        )
    )
    orchestrator.build_index(PipelineIndexRequest(corpus_ids=prepared.corpus_ids))
    corpus = orchestrator.repository.get_corpus(prepared.corpus_ids[0])
    result = orchestrator.retriever.retrieve_with_scores(
        corpus,
        top_k=orchestrator.settings.top_k,
        exclude_practice=orchestrator.settings.exclude_practice_examples,
    )
    assert result.query
    assert result.hits
    assert all(hit.corpus_id == corpus.corpus_id for hit in result.hits)
    assert [hit.rank for hit in result.hits] == list(range(1, len(result.hits) + 1))
