from __future__ import annotations

import hashlib
import math
import os
import re

from openai import OpenAI
import tiktoken

from stt_quiz_service.config import Settings


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_]+")


class BaseEmbedder:
    provider_name = "base"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class HashEmbedder(BaseEmbedder):
    provider_name = "hash"

    def __init__(self, dim: int):
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in TOKEN_RE.findall(text.lower()):
            hashed = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = hashed % self.dim
            vector[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class OpenAIEmbedder(BaseEmbedder):
    provider_name = "openai"
    MAX_TOKENS_PER_TEXT = 8192

    def __init__(self, model: str, *, max_batch_tokens: int = 250_000, max_batch_texts: int = 128):
        self.client = OpenAI()
        self.model = model
        self.max_batch_tokens = max_batch_tokens
        self.max_batch_texts = max_batch_texts
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except Exception:
            self.encoding = None

    def _truncate_text(self, text: str) -> str:
        """Truncate text so it does not exceed MAX_TOKENS_PER_TEXT tokens."""
        if self.encoding is None:
            # Rough char-based fallback: ~4 chars per token
            max_chars = self.MAX_TOKENS_PER_TEXT * 4
            return text[: max_chars]
        tokens = self.encoding.encode(text)
        if len(tokens) <= self.MAX_TOKENS_PER_TEXT:
            return text
        return self.encoding.decode(tokens[: self.MAX_TOKENS_PER_TEXT])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        truncated = [self._truncate_text(t) for t in texts]
        embeddings: list[list[float]] = []
        for batch in self._batch_texts(truncated):
            response = self.client.embeddings.create(model=self.model, input=batch)
            embeddings.extend(item.embedding for item in response.data)
        return embeddings

    def _estimate_tokens(self, text: str) -> int:
        if self.encoding is None:
            return max(1, len(text) // 4)
        return len(self.encoding.encode(text))

    def _batch_texts(self, texts: list[str]) -> list[list[str]]:
        batches: list[list[str]] = []
        current_batch: list[str] = []
        current_tokens = 0

        for text in texts:
            token_count = self._estimate_tokens(text)
            if current_batch and (
                current_tokens + token_count > self.max_batch_tokens
                or len(current_batch) >= self.max_batch_texts
            ):
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(text)
            current_tokens += token_count

        if current_batch:
            batches.append(current_batch)
        return batches


def build_embedder(settings: Settings) -> BaseEmbedder:
    backend = settings.embedding_backend.lower()
    if backend == "hash":
        return HashEmbedder(settings.embedding_dim)
    if backend == "openai":
        return OpenAIEmbedder(settings.openai_embedding_model)
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIEmbedder(settings.openai_embedding_model)
    return HashEmbedder(settings.embedding_dim)
