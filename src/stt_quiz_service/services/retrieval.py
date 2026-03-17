from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from stt_quiz_service.schemas import ChunkDocument, RetrievalHit
from stt_quiz_service.storage.repository import CorpusSelection, Repository
from stt_quiz_service.services.embeddings import BaseEmbedder


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_]{2,}")


def extract_concepts(corpus: CorpusSelection, chunks: list[ChunkDocument]) -> list[str]:
    seed_parts = [corpus.content, corpus.learning_goal]
    concepts: list[str] = []
    for part in seed_parts:
        concepts.extend([token.strip() for token in re.split(r"[,/]", part) if token.strip()])
    if concepts:
        return list(dict.fromkeys(concepts))[:8]
    counter: Counter[str] = Counter()
    for chunk in chunks:
        counter.update(TOKEN_RE.findall(chunk.text))
    return [token for token, _ in counter.most_common(8)]


def build_retrieval_query(corpus: CorpusSelection, chunks: list[ChunkDocument]) -> str:
    concepts = extract_concepts(corpus, chunks)
    return " ".join(
        [
            corpus.subject,
            corpus.content,
            corpus.learning_goal,
            corpus.summary,
            " ".join(concepts),
        ]
    ).strip()


@dataclass(slots=True)
class RetrievalResult:
    query: str
    hits: list[RetrievalHit]


class Retriever:
    def __init__(self, repository: Repository, embedder: BaseEmbedder):
        self.repository = repository
        self.embedder = embedder

    def retrieve_with_scores(
        self,
        corpus: CorpusSelection,
        *,
        top_k: int,
        exclude_practice: bool,
    ) -> RetrievalResult:
        all_chunks = self.repository.get_chunks_for_corpus(corpus.corpus_id)
        query = build_retrieval_query(corpus, all_chunks)
        query_vector = self.embedder.embed_query(query)
        hits = self.repository.search_chunks(
            corpus.corpus_id,
            query_vector,
            top_k=top_k,
            exclude_practice=exclude_practice,
        )
        return RetrievalResult(query=query, hits=hits)

    def retrieve(
        self,
        corpus: CorpusSelection,
        *,
        top_k: int,
        exclude_practice: bool,
    ) -> list[ChunkDocument]:
        result = self.retrieve_with_scores(
            corpus,
            top_k=top_k,
            exclude_practice=exclude_practice,
        )
        return [hit.to_chunk_document() for hit in result.hits]
