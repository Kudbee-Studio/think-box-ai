"""Tests for the embeddings service (Issue #8 Stage 4 / Issue #9 enabler)."""

from __future__ import annotations

import unittest

from core.memory.embeddings import EmbeddingService


class TestEmbeddingService(unittest.TestCase):
    """Test embedding generation (fallback mode when no ML deps)."""

    def setUp(self) -> None:
        self.service = EmbeddingService()

    def test_dimension(self) -> None:
        self.assertEqual(self.service.dimension, 1536)

    def test_embed_returns_vector(self) -> None:
        vector = self.service.embed("PostgreSQL preferred over Redis")
        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 1536)

    def test_embed_deterministic(self) -> None:
        v1 = self.service.embed("same text")
        v2 = self.service.embed("same text")
        self.assertEqual(v1, v2)

    def test_embed_different_texts_differ(self) -> None:
        v1 = self.service.embed("database choice A")
        v2 = self.service.embed("completely different topic about cats")
        self.assertNotEqual(v1, v2)

    def test_embed_normalized(self) -> None:
        vector = self.service.embed("normalize me")
        norm = sum(x * x for x in vector) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_embed_batch(self) -> None:
        vectors = self.service.embed_batch(["text one", "text two", "text three"])
        self.assertEqual(len(vectors), 3)
        for v in vectors:
            self.assertEqual(len(v), 1536)

    def test_empty_text(self) -> None:
        vector = self.service.embed("")
        self.assertEqual(len(vector), 1536)


if __name__ == "__main__":
    unittest.main()
