from __future__ import annotations

from types import SimpleNamespace

from stt_quiz_service.services.embeddings import OpenAIEmbedder


class _FakeEmbeddingsAPI:
    def __init__(self):
        self.calls: list[list[str]] = []

    def create(self, *, model: str, input: list[str]):
        self.calls.append(list(input))
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(idx)]) for idx, _ in enumerate(input, start=1)]
        )


def test_openai_embedder_batches_large_requests():
    embedder = OpenAIEmbedder("text-embedding-3-small", max_batch_tokens=10, max_batch_texts=2)
    fake_api = _FakeEmbeddingsAPI()
    embedder.client = SimpleNamespace(embeddings=fake_api)
    embedder._estimate_tokens = lambda text: 6 if text != "tiny" else 1

    vectors = embedder.embed_documents(["first", "second", "tiny"])

    assert len(fake_api.calls) == 2
    assert fake_api.calls[0] == ["first"]
    assert fake_api.calls[1] == ["second", "tiny"]
    assert vectors == [[1.0], [1.0], [2.0]]
