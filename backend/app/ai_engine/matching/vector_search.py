"""
Module 7 – Vector Search & In-Memory Similarity Index
=====================================================
High-performance, thread-safe vector similarity index for candidate retrieval.
Supports dataset filtering (Missing Person Dataset vs. Wanted Person Dataset),
department scoping, and fast vectorized batch matrix operations.

AI Safety Invariant:
--------------------
Enforces logical separation between Missing Person and Wanted Person records.
Searches only query authorized active cases and reference images.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
from typing import Sequence

import numpy as np

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.matching.similarity import similarity_calculator
from app.ai_engine.schemas.matching import (
    ReferenceEmbeddingRecord,
    SearchMode,
    SimilarityMetric,
)

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Individual vector match outcome."""

    record: ReferenceEmbeddingRecord
    similarity_score: float


class VectorSearchIndex:
    """
    In-memory vector database and similarity index supporting dynamic insertions,
    deletions, metadata filtering, and optimized vectorized batch matrix queries.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # image_id -> ReferenceEmbeddingRecord
        self._records: dict[int, ReferenceEmbeddingRecord] = {}
        # image_id -> np.ndarray (shape: D)
        self._vectors: dict[int, np.ndarray] = {}

        # Cached contiguous matrix for vectorized matrix dot products
        self._dirty: bool = True
        self._cached_image_ids: list[int] = []
        self._cached_matrix: np.ndarray = np.empty((0, 0), dtype=np.float32)

    def add_embedding(
        self, record: ReferenceEmbeddingRecord, vector: np.ndarray
    ) -> None:
        """
        Enroll or update a reference embedding in the search index.
        """
        with self._lock:
            # Ensure float32 and L2-normalized
            v_norm = np.linalg.norm(vector)
            if v_norm > 1e-10:
                normalized_v = (vector / v_norm).astype(np.float32)
            else:
                normalized_v = vector.astype(np.float32)

            self._records[record.image_id] = record
            self._vectors[record.image_id] = normalized_v
            self._dirty = True

    def remove_embedding(self, image_id: int) -> bool:
        """Prune an embedding when a reference image is deleted or deactivated."""
        with self._lock:
            removed = bool(self._records.pop(image_id, None))
            self._vectors.pop(image_id, None)
            if removed:
                self._dirty = True
            return removed

    def remove_case_embeddings(self, case_id: int) -> int:
        """Prune all embeddings associated with a closed or deactivated case."""
        with self._lock:
            to_remove = [
                img_id
                for img_id, rec in self._records.items()
                if rec.case_id == case_id
            ]
            for img_id in to_remove:
                self._records.pop(img_id, None)
                self._vectors.pop(img_id, None)
            if to_remove:
                self._dirty = True
            return len(to_remove)

    def clear(self) -> None:
        """Flush the search index."""
        with self._lock:
            self._records.clear()
            self._vectors.clear()
            self._dirty = True
            self._cached_image_ids.clear()
            self._cached_matrix = np.empty((0, 0), dtype=np.float32)

    def _sync_cache_if_dirty(self) -> None:
        """Rebuilds contiguous NumPy matrix for ultra-fast vectorized retrieval."""
        if not self._dirty:
            return

        with self._lock:
            if not self._dirty:
                return
            self._cached_image_ids = list(self._records.keys())
            if self._cached_image_ids:
                matrix_list = [self._vectors[iid] for iid in self._cached_image_ids]
                self._cached_matrix = np.vstack(matrix_list).astype(np.float32)
            else:
                self._cached_matrix = np.empty((0, 0), dtype=np.float32)
            self._dirty = False

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int | None = None,
        mode: SearchMode | str = SearchMode.ALL_ACTIVE_CASES,
        department_id: int | None = None,
        metric: SimilarityMetric | str | None = None,
    ) -> list[VectorSearchResult]:
        """
        Searches the index for nearest reference embeddings matching query_vector.
        Enforces category isolation (MISSING vs WANTED) and department constraints.
        """
        k = top_k or matching_settings.TOP_K_CANDIDATES
        mode_enum = SearchMode(mode) if isinstance(mode, str) else mode
        metric_enum = (
            SimilarityMetric(metric.upper())
            if isinstance(metric, str)
            else (metric or similarity_calculator.default_metric)
        )

        with self._lock:
            self._sync_cache_if_dirty()

            if not self._cached_image_ids:
                return []

            # 1. Compute vectorized batch similarities across all index entries
            sims = similarity_calculator.compute_batch_similarity(
                query_vector=query_vector,
                reference_matrix=self._cached_matrix,
                metric=metric_enum,
            )

            # 2. Filter candidates based on SearchMode and department
            filtered_results: list[VectorSearchResult] = []
            for idx, img_id in enumerate(self._cached_image_ids):
                rec = self._records[img_id]

                # Verify active status
                if not rec.is_active:
                    continue

                # Category isolation: MISSING vs WANTED
                if mode_enum == SearchMode.MISSING and rec.category != "MISSING":
                    continue
                if mode_enum == SearchMode.WANTED and rec.category != "WANTED":
                    continue

                # Department scoping
                if department_id is not None and rec.department_id != department_id:
                    continue

                filtered_results.append(
                    VectorSearchResult(
                        record=rec,
                        similarity_score=float(sims[idx]),
                    )
                )

            # 3. Sort descending by similarity and take top_k
            filtered_results.sort(key=lambda x: x.similarity_score, reverse=True)
            return filtered_results[:k]

    def count_active(self, mode: SearchMode | str = SearchMode.ALL_ACTIVE_CASES) -> int:
        """Returns the total number of active searchable embeddings in the index."""
        mode_enum = SearchMode(mode) if isinstance(mode, str) else mode
        with self._lock:
            if mode_enum == SearchMode.ALL_ACTIVE_CASES:
                return sum(1 for r in self._records.values() if r.is_active)
            elif mode_enum == SearchMode.MISSING:
                return sum(1 for r in self._records.values() if r.is_active and r.category == "MISSING")
            elif mode_enum == SearchMode.WANTED:
                return sum(1 for r in self._records.values() if r.is_active and r.category == "WANTED")
            return 0

    def get_all_records(self) -> list[ReferenceEmbeddingRecord]:
        """Returns a snapshot of all enrolled reference records."""
        with self._lock:
            return list(self._records.values())


# Module-level singleton
vector_search_index = VectorSearchIndex()
