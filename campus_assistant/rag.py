"""Small, inspectable embedding-based retriever for campus rules."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=list(texts))
        return [item.embedding for item in response.data]


@dataclass(frozen=True)
class RuleChunk:
    section: str
    text: str

    @property
    def embedding_text(self) -> str:
        return f"{self.section}\n{self.text}"


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


class RuleRetriever:
    def __init__(
        self,
        rules_path: Path | str,
        cache_path: Path | str,
        provider: EmbeddingProvider,
        model: str,
    ):
        self.rules_path = Path(rules_path)
        self.cache_path = Path(cache_path)
        self.provider = provider
        self.model = model
        self.chunks = self._load_chunks()
        self._vectors: list[list[float]] | None = None

    def _load_chunks(self) -> list[RuleChunk]:
        raw = self.rules_path.read_text(encoding="utf-8")
        chunks: list[RuleChunk] = []
        current_heading = "場地規範"
        current_lines: list[str] = []

        def flush() -> None:
            body = "\n".join(line for line in current_lines if line.strip()).strip()
            if body:
                chunks.append(RuleChunk(section=current_heading, text=body))

        for line in raw.splitlines():
            if line.startswith("## "):
                flush()
                current_heading = line[3:].strip()
                current_lines = []
            elif not line.startswith("# "):
                current_lines.append(line)
        flush()
        if not chunks:
            raise ValueError(f"No rule sections found in {self.rules_path}")
        return chunks

    def _source_hash(self) -> str:
        return hashlib.sha256(self.rules_path.read_bytes()).hexdigest()

    def _load_cached_vectors(self) -> list[list[float]] | None:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        if (
            payload.get("source_sha256") != self._source_hash()
            or payload.get("model") != self.model
            or len(payload.get("vectors", [])) != len(self.chunks)
        ):
            return None
        return payload["vectors"]

    def _ensure_vectors(self) -> list[list[float]]:
        if self._vectors is not None:
            return self._vectors
        cached = self._load_cached_vectors()
        if cached is not None:
            self._vectors = cached
            return cached

        vectors = self.provider.embed([chunk.embedding_text for chunk in self.chunks])
        if len(vectors) != len(self.chunks):
            raise RuntimeError("Embedding service returned an unexpected vector count.")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(
                {
                    "source_sha256": self._source_hash(),
                    "model": self.model,
                    "vectors": vectors,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self._vectors = vectors
        return vectors

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        vectors = self._ensure_vectors()
        query_vector = self.provider.embed([query])[0]
        scored = [
            (_cosine_similarity(query_vector, vector), index)
            for index, vector in enumerate(vectors)
        ]
        results: list[dict[str, Any]] = []
        for score, index in sorted(scored, reverse=True)[: max(1, min(top_k, 5))]:
            chunk = self.chunks[index]
            results.append(
                {
                    "section": f"校園空間使用規範（模擬資料）－{chunk.section}",
                    "text": chunk.text,
                    "score": round(score, 4),
                }
            )
        return results
