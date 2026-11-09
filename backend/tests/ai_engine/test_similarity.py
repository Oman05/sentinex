"""
Tests for Module 7 – Vector Similarity Calculation
===================================================
Verifies Cosine Similarity, Euclidean Distance conversion, batch operations,
boundary invariants, and metric overrides.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ai_engine.matching.similarity import SimilarityCalculator
from app.ai_engine.schemas.matching import SimilarityMetric


@pytest.fixture
def sim_calc():
    return SimilarityCalculator()


class TestCosineSimilarity:

    def test_identical_unit_vectors_return_one(self, sim_calc):
        v = np.random.randn(512).astype(np.float32)
        v /= np.linalg.norm(v)
        sim = sim_calc.cosine_similarity(v, v)
        assert pytest.approx(sim, abs=1e-4) == 1.0

    def test_orthogonal_vectors_return_zero(self, sim_calc):
        v1 = np.zeros(512, dtype=np.float32)
        v2 = np.zeros(512, dtype=np.float32)
        v1[0] = 1.0
        v2[1] = 1.0
        sim = sim_calc.cosine_similarity(v1, v2)
        assert pytest.approx(sim, abs=1e-4) == 0.0

    def test_opposite_vectors_clipped_to_zero(self, sim_calc):
        v1 = np.ones(512, dtype=np.float32)
        v1 /= np.linalg.norm(v1)
        v2 = -v1
        sim = sim_calc.cosine_similarity(v1, v2)
        assert sim == 0.0

    def test_score_always_bounded_in_zero_to_one(self, sim_calc):
        rng = np.random.default_rng(42)
        for _ in range(50):
            v1 = rng.standard_normal(512).astype(np.float32)
            v2 = rng.standard_normal(512).astype(np.float32)
            sim = sim_calc.cosine_similarity(v1, v2)
            assert 0.0 <= sim <= 1.0

    def test_empty_or_none_vector_handling(self, sim_calc):
        v = np.ones(512, dtype=np.float32)
        assert sim_calc.cosine_similarity(None, v) == 0.0
        assert sim_calc.cosine_similarity(v, None) == 0.0
        assert sim_calc.cosine_similarity(np.empty(0), v) == 0.0


class TestEuclideanDistance:

    def test_identical_vectors_have_zero_distance(self, sim_calc):
        v = np.ones(512, dtype=np.float32)
        dist = sim_calc.euclidean_distance(v, v)
        assert dist == 0.0
        assert sim_calc.euclidean_to_similarity(dist) == 1.0

    def test_far_vectors_have_lower_similarity(self, sim_calc):
        v1 = np.zeros(512, dtype=np.float32)
        v2 = np.ones(512, dtype=np.float32) * 10.0
        dist = sim_calc.euclidean_distance(v1, v2)
        sim = sim_calc.euclidean_to_similarity(dist)
        assert 0.0 < sim < 0.10

    def test_none_handling(self, sim_calc):
        v = np.ones(512, dtype=np.float32)
        assert sim_calc.euclidean_distance(None, v) == float("inf")


class TestBatchSimilarity:

    def test_batch_matches_single_cosine(self, sim_calc):
        rng = np.random.default_rng(123)
        query = rng.standard_normal(512).astype(np.float32)
        query /= np.linalg.norm(query)

        matrix = rng.standard_normal((10, 512)).astype(np.float32)
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)

        batch_sims = sim_calc.compute_batch_similarity(query, matrix, metric=SimilarityMetric.COSINE)
        assert len(batch_sims) == 10

        for i in range(10):
            single_sim = sim_calc.cosine_similarity(query, matrix[i])
            assert pytest.approx(batch_sims[i], abs=1e-3) == single_sim

    def test_batch_matches_single_euclidean(self, sim_calc):
        rng = np.random.default_rng(456)
        query = rng.standard_normal(512).astype(np.float32)
        query /= np.linalg.norm(query)

        matrix = rng.standard_normal((5, 512)).astype(np.float32)
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)

        batch_sims = sim_calc.compute_batch_similarity(query, matrix, metric=SimilarityMetric.EUCLIDEAN)
        assert len(batch_sims) == 5

        for i in range(5):
            single_sim = sim_calc.compute_similarity(query, matrix[i], metric=SimilarityMetric.EUCLIDEAN)
            assert pytest.approx(batch_sims[i], abs=1e-3) == single_sim

    def test_batch_empty_matrix(self, sim_calc):
        query = np.ones(512, dtype=np.float32)
        matrix = np.empty((0, 512), dtype=np.float32)
        batch_sims = sim_calc.compute_batch_similarity(query, matrix)
        assert len(batch_sims) == 0
