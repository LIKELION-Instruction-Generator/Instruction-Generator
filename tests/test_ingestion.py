from __future__ import annotations

from stt_quiz_service.schemas import GenerateBundleRequest, PipelineGenerateRequest, PipelineIndexRequest, PipelinePrepareRequest


def _prepare(orchestrator, tmp_path):
    return orchestrator.prepare_corpus(
        PipelinePrepareRequest(
            transcripts_root=str(orchestrator.settings.transcripts_root),
            curriculum_path=str(orchestrator.settings.curriculum_path),
            output_dir=str(tmp_path / "prepared"),
        )
    )


def test_ingest_builds_sessions_and_chunks(orchestrator, tmp_path):
    response = _prepare(orchestrator, tmp_path)
    assert response.corpora_prepared >= 1
    assert response.targets_prepared >= 3
    corpora = orchestrator.list_lectures()
    corpus_ids = {corpus.corpus_id for corpus in corpora}
    assert "2026-02-24" in corpus_ids


def test_practice_examples_are_tagged(orchestrator, tmp_path):
    prepared = _prepare(orchestrator, tmp_path)
    all_chunks = []
    for corpus_id in prepared.corpus_ids:
        all_chunks.extend(orchestrator.repository.get_chunks_for_corpus(corpus_id))
    assert any(chunk.practice_example for chunk in all_chunks)


def test_bundle_generation_is_schema_valid(orchestrator, tmp_path):
    prepared = _prepare(orchestrator, tmp_path)
    orchestrator.build_index(PipelineIndexRequest(corpus_ids=prepared.corpus_ids))
    corpus_id = prepared.corpus_ids[0]
    bundle = orchestrator.generate_bundle(
        GenerateBundleRequest(corpus_id=corpus_id, mode="rag", num_questions=5, choice_count=None)
    )
    assert len(bundle.quiz_set.items) >= 5
    assert bundle.study_guide.key_concepts
    assert bundle.run.evaluation is not None
    assert bundle.run.retrieval_query
    assert bundle.run.retrieval_hits
    assert len({item.question_profile for item in bundle.quiz_set.items}) >= 2
    assert all(item.choice_count == len(item.options) for item in bundle.quiz_set.items)

def test_latest_bundle_is_loadable(orchestrator, tmp_path):
    prepared = _prepare(orchestrator, tmp_path)
    orchestrator.build_index(PipelineIndexRequest(corpus_ids=prepared.corpus_ids))
    corpus_id = prepared.corpus_ids[0]
    runs = orchestrator.generate_artifacts(
        PipelineGenerateRequest(
            corpus_ids=[corpus_id],
            mode="rag",
            num_questions=5,
            choice_count=None,
        )
    )
    assert runs
    stored = orchestrator.get_latest_bundle(corpus_id)
    assert stored.quiz_set.items
    assert stored.study_guide.key_concepts


def test_prepare_exports_files_without_touching_db(orchestrator, tmp_path):
    compare_output = tmp_path / "prepared_export_only"
    response = orchestrator.prepare_corpus(
        PipelinePrepareRequest(
            transcripts_root=str(orchestrator.settings.transcripts_root),
            curriculum_path=str(orchestrator.settings.curriculum_path),
            output_dir=str(compare_output),
            persist_to_db=False,
        )
    )

    assert response.corpora_prepared >= 1
    assert response.skipped is False
    assert (compare_output / "_prepare_manifest.json").exists()
    assert all((compare_output / f"{corpus_id}.txt").exists() for corpus_id in response.corpus_ids)
    assert orchestrator.repository.list_corpora() == []
