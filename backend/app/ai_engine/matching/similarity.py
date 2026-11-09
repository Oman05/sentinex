"""
Module 7 – Vector Similarity Calculation
=========================================
Computes mathematical proximity between query and reference feature vectors.
Supports both Cosine Similarity and Euclidean Distance.

AI Safety Invariant:
--------------------
Similarity scores represent algorithmic feature vector alignment.
They MUST NEVER be presented as guaranteed identity probabilities
(e.g., never display "95% probability this is the person").
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.schemas.matching import SimilarityMetric

logger = logging.getLogger(__name__)


class SimilarityCalculator:
    """
    Computes distance and similarity metrics between face feature vectors.
    Optimized for both single pair comparisons and high-throughput batch matrices.
    """

    def __init__(self, default_metric: SimilarityMetric | str | None = None) -> None:
        metric_str = (default_metric or matching_settings.SIMILARITY_METRIC).upper()
        self.default_metric = (
            SimilarityMetric.EUCLIDEAN
            if metric_str == "EUCLIDEAN"
            else SimilarityMetric.COSINE
        )

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """
        Calculates cosine similarity between two 1D vectors.
        Assuming L2-normalized inputs, cos(theta) = dot(a, b).
        Maps raw cosine [-1.0, 1.0] into bounded similarity score [0.0, 1.0].
        """
        if vec_a is None or vec_b is None or len(vec_a) == 0 or len(vec_b) == 0:
            return 0.0

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0

        dot = float(np.dot(vec_a, vec_b))
        raw_cos = dot / (norm_a * norm_b)
        # Numerical guard
        raw_cos = max(-1.0, min(1.0, raw_cos))
        # Map [-1.0, 1.0] to [0.0, 1.0]
        # For facial recognition, negative or orthogonal similarities represent non-matches (0.0)
        similarity = max(0.0, float(raw_cos))
        return round(similarity, 4)

    @staticmethod
    def euclidean_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculates standard Euclidean (L2) distance between two vectors."""
        if vec_a is None or vec_b is None or len(vec_a) == 0 or len(vec_b) == 0:
            return float("inf")
        dist = float(np.linalg.norm(vec_a - vec_b))
        return round(dist, 4)

    @classmethod
    def euclidean_to_similarity(cls, distance: float) -> float:
        """
        Converts Euclidean distance to a bounded similarity metric in [0.0, 1.0].
        Formula: sim = 1.0 / (1.0 + distance).
        For identical unit vectors (dist=0.0) -> 1.0.
        """
        if distance < 0:
            return 0.0
        sim = 1.0 / (1.0 + distance)
        return round(float(sim), 4)

    def compute_similarity(
        self,
        query_vector: np.ndarray,
        reference_vector: np.ndarray,
        metric: SimilarityMetric | str | None = None,
    ) -> float:
        """Compute similarity score between query and reference using selected metric."""
        metric_enum = (
            SimilarityMetric(metric.upper())
            if isinstance(metric, str)
            else (metric or self.default_metric)
        )

        if metric_enum == SimilarityMetric.EUCLIDEAN:
            dist = self.euclidean_distance(query_vector, reference_vector)
            return self.euclidean_to_similarity(dist)
        else:
            return self.cosine_similarity(query_vector, reference_vector)

    def compute_batch_similarity(
        self,
        query_vector: np.ndarray,
        reference_matrix: np.ndarray,
        metric: SimilarityMetric | str | None = None,
    ) -> np.ndarray:
        """
        Vectorized batch similarity computation against a matrix of references.
        query_vector: shape (D,)
        reference_matrix: shape (N, D)
        Returns: 1D array of similarity scores of shape (N,) in range [0.0, 1.0].
        """
        if reference_matrix.size == 0 or query_vector.size == 0:
            return np.empty(0, dtype=np.float32)

        metric_enum = (
            SimilarityMetric(metric.upper())
            if isinstance(metric, str)
            else (metric or self.default_metric)
        )

        # Ensure query is 1D and unit normalized
        q_norm = np.linalg.norm(query_vector)
        q = (query_vector / (q_norm + 1e-10)).astype(np.float32)

        if metric_enum == SimilarityMetric.EUCLIDEAN:
            # Vectorized euclidean distance: sqrt(sum((R - q)^2, axis=1))
            diffs = reference_matrix - q
            dists = np.linalg.norm(diffs, axis=1)
            sims = 1.0 / (1.0 + dists)
            return np.clip(sims, 0.0, 1.0).astype(np.float32)
        else:
            # Normalize reference matrix rows if not already normalized
            r_norms = np.linalg.norm(reference_matrix, axis=1, keepdims=True)
            r_norms[r_norms < 1e-10] = 1.0
            r_normalized = reference_matrix / r_norms

            # Fast matrix-vector dot product (N, D) @ (D,) -> (N,)
            raw_dots = np.dot(r_normalized, q)
            # Clip negative dot products to 0.0
            sims = np.maximum(0.0, raw_dots)
            return np.clip(sims, 0.0, 1.0).astype(np.float32)


# Module-level singleton
similarity_calculator = SimilarityCalculator()
