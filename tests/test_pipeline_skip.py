from __future__ import annotations

from stt_quiz_service.schemas import PipelineGenerateRequest, PipelineIndexRequest, PipelinePrepareRequest


def test_prepare_and_index_skip_when_inputs_are_unchanged(orchestrator, tmp_path):
    prepare_request = PipelinePrepareRequest(
        transcripts_root=str(orchestrator.settings.transcripts_root),
        curriculum_path=str(orchestrator.settings.curriculum_path),
        output_dir=str(tmp_path / "prepared"),
    )

    first_prepare = orchestrator.prepare_corpus(prepare_request)
    second_prepare = orchestrator.prepare_corpus(prepare_request)

    assert first_prepare.skipped is False
    assert second_prepare.skipped is True
    assert second_prepare.corpus_ids == first_prepare.corpus_ids

    first_index = orchestrator.build_index(PipelineIndexRequest(corpus_ids=first_prepare.corpus_ids))
    second_index = orchestrator.build_index(PipelineIndexRequest(corpus_ids=first_prepare.corpus_ids))

    assert first_index.skipped is False
    assert second_index.skipped is True


def test_generate_skips_when_same_bundle_already_exists(orchestrator, tmp_path):
    prepare_request = PipelinePrepareRequest(
        transcripts_root=str(orchestrator.settings.transcripts_root),
        curriculum_path=str(orchestrator.settings.curriculum_path),
        output_dir=str(tmp_path / "prepared"),
    )
    prepared = orchestrator.prepare_corpus(prepare_request)
    orchestrator.build_index(PipelineIndexRequest(corpus_ids=prepared.corpus_ids))

    request = PipelineGenerateRequest(
        corpus_ids=[prepared.corpus_ids[0]],
        mode="rag",
        num_questions=5,
        choice_count=None,
    )

    first_runs = orchestrator.generate_artifacts(request)
    second_runs = orchestrator.generate_artifacts(request)

    assert len(first_runs) == 1
    assert len(second_runs) == 1
    assert second_runs[0].run_id == first_runs[0].run_id


def test_prepare_export_skips_when_same_export_already_exists(orchestrator, tmp_path):
    prepare_request = PipelinePrepareRequest(
        transcripts_root=str(orchestrator.settings.transcripts_root),
        curriculum_path=str(orchestrator.settings.curriculum_path),
        output_dir=str(tmp_path / "prepared_export_only"),
        persist_to_db=False,
    )

    first_prepare = orchestrator.prepare_corpus(prepare_request)
    second_prepare = orchestrator.prepare_corpus(prepare_request)

    assert first_prepare.skipped is False
    assert second_prepare.skipped is True
    assert second_prepare.corpus_ids == first_prepare.corpus_ids
