from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from campus_assistant.rag import RuleRetriever


class KeywordEmbeddingProvider:
    vocabulary = ("飲食", "取消", "設備", "開放", "預約")

    def embed(self, texts):
        return [
            [float(text.count(token)) for token in self.vocabulary]
            for text in texts
        ]


class RuleRetrieverTests(unittest.TestCase):
    def test_returns_relevant_section_and_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).resolve().parents[1]
            cache = Path(temp_dir) / "index.json"
            retriever = RuleRetriever(
                root / "data" / "campus_rules.md",
                cache,
                KeywordEmbeddingProvider(),
                "fake-embedding",
            )
            result = retriever.search("圖書館可以飲食嗎？", top_k=1)
            self.assertIn("飲食與清潔", result[0]["section"])
            self.assertTrue(cache.exists())


if __name__ == "__main__":
    unittest.main()
