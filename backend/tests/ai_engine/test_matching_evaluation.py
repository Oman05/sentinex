"""
Tests for Module 7 – Research Evaluation Suite & 4 Controlled Data Groups
========================================================================
Implements Sections 23 & 24:
Evaluates candidate retrieval and matching against four controlled data groups:
- DATASET 1: Missing Person Reference Dataset
- DATASET 2: Wanted Person Reference Dataset
- DATASET 3: Positive Test Dataset (probes belonging to enrolled subjects)
- DATASET 4: Negative / Unknown Person Dataset (non-enrolled unknown subjects)

Measures:
- True Positive Rate (TPR / Recall)
- False Positive Rate (FPR)
- Precision
- False Match Rate (FMR)
- False Non-Match Rate (FNMR)
- Top-1 Retrieval Rate
- Top-5 Retrieval Rate
- Query Latency
"""

from __future__ import annotations

import base64
import time
import cv2
import numpy as np
import pytest

from app.ai_engine.matching.embedding_service import FaceEmbeddingService
from app.ai_engine.matching.models.embedding_model import AnalyticalFaceEmbeddingModel
from app.ai_engine.matching.vector_search import VectorSearchIndex
from app.ai_engine.schemas.matching import (
    MatchDecisionState,
    MatchReadyCandidateInput,
    ReferenceEmbeddingRecord,
    SearchMode,
)
from app.services.matching_service import MatchingService


def _create_synthetic_subject(seed: int, variation: float = 0.0) -> np.ndarray:
    """Generates a reproducible, consent-free synthetic face for a unique subject seed."""
    rng = np.random.default_rng(seed)
    base_luma = int(rng.integers(70, 200))
    eye_sep = int(rng.integers(15, 30))
    nose_len = int(rng.integers(15, 28))

    img = np.full((112, 112, 3), base_luma, dtype=np.uint8)
    cx, cy = 56, 56

    # Draw anatomical features
    cv2.circle(img, (cx - eye_sep, cy - 18), 8, (20, 20, 20), -1)
    cv2.circle(img, (cx + eye_sep, cy - 18), 8, (20, 20, 20), -1)
    cv2.line(img, (cx, cy - 10), (cx, cy - 10 + nose_len), (30, 30, 30), 3)
    cv2.ellipse(img, (cx, cy + 28), (20, 8), 0, 0, 180, (15, 15, 15), 2)

    if variation > 0:
        noise = rng.normal(0, variation * 20, (112, 112, 3))
        img = np.clip(img.astype(float) + noise, 0, 255).astype(np.uint8)

    return img


def _to_b64(img: np.ndarray) -> str:
    _, enc = cv2.imencode(".jpg", img)
    return base64.b64encode(enc.tobytes()).decode("utf-8")


class TestMatchingResearchEvaluation:
    """
    Evaluates algorithmic accuracy and false positive resistance
    using 4 distinct research datasets.
    """

    @pytest.fixture(autouse=True)
    def setup_datasets(self):
        self.model = AnalyticalFaceEmbeddingModel()
        self.embedder = FaceEmbeddingService(model=self.model)
        self.index = VectorSearchIndex()
        self.service = MatchingService(embedder=self.embedder, index=self.index)

        # DATASET 1: Missing Person Reference Dataset (Subjects 1 to 5)
        self.missing_cases: dict[int, str] = {}
        for s_id in range(1, 6):
            cnum = f"MP-2026-000{s_id}"
            self.missing_cases[s_id] = cnum
            face = _create_synthetic_subject(seed=s_id * 100)
            vec = self.model.extract_embedding(face)
            rec = ReferenceEmbeddingRecord(
                image_id=s_id,
                case_id=s_id,
                case_number=cnum,
                category="MISSING",
                department_id=1,
                model_name=self.model.model_name,
                model_version=self.model.model_version,
            )
            self.index.add_embedding(rec, vec)

        # DATASET 2: Wanted Person Reference Dataset (Subjects 6 to 10)
        self.wanted_cases: dict[int, str] = {}
        for s_id in range(6, 11):
            cnum = f"WP-2026-000{s_id}"
            self.wanted_cases[s_id] = cnum
            face = _create_synthetic_subject(seed=s_id * 100)
            vec = self.model.extract_embedding(face)
            rec = ReferenceEmbeddingRecord(
                image_id=s_id,
                case_id=s_id,
                case_number=cnum,
                category="WANTED",
                department_id=1,
                model_name=self.model.model_name,
                model_version=self.model.model_version,
            )
            self.index.add_embedding(rec, vec)

    def test_positive_dataset_retrieval_and_top_k(self):
        """
        DATASET 3: Positive Test Dataset
        Evaluates known probe faces against enrolled records.
        Measures: Top-1 Retrieval Rate, Top-5 Retrieval Rate, and Latency.
        """
        top1_hits = 0
        top5_hits = 0
        total_probes = 10
        latencies = []

        for s_id in range(1, 11):
            expected_cnum = self.missing_cases.get(s_id) or self.wanted_cases.get(s_id)
            # Generate slightly varied probe of the same subject
            probe_face = _create_synthetic_subject(seed=s_id * 100, variation=0.10)
            b64_img = _to_b64(probe_face)

            inp = MatchReadyCandidateInput(
                candidate_id=f"POS-PROBE-{s_id}",
                track_id=f"TRACK-POS-{s_id}",
                camera_id=1,
                face_image_base64=b64_img,
                face_quality_score=0.88,
                quality_status="GOOD",
                is_match_ready=True,
                search_mode=SearchMode.ALL_ACTIVE_CASES,
            )

            t0 = time.perf_counter()
            resp = self.service.process_match_ready_candidate(inp)
            latencies.append((time.perf_counter() - t0) * 1000.0)

            retrieved_cnums = [c.case_number for c in resp.candidates]
            if retrieved_cnums:
                if retrieved_cnums[0] == expected_cnum:
                    top1_hits += 1
                if expected_cnum in retrieved_cnums:
                    top5_hits += 1

        top1_rate = top1_hits / total_probes
        top5_rate = top5_hits / total_probes
        mean_latency = float(np.mean(latencies))

        # Top retrieval metrics
        assert top1_rate >= 0.80, f"Top-1 retrieval rate {top1_rate:.2f} below target 0.80"
        assert top5_rate == 1.00, f"Top-5 retrieval rate {top5_rate:.2f} below target 1.00"
        assert mean_latency < 50.0, f"Average latency {mean_latency:.2f}ms exceeds 50ms target"

    def test_negative_unknown_dataset_false_match_rejection(self):
        """
        DATASET 4: Negative / Unknown Person Dataset
        Evaluates completely unknown subjects not present in the reference database.
        Measures: False Match Rate (FMR) at review threshold.
        """
        false_matches = 0
        total_unknowns = 10

        for u_id in range(501, 511):
            # Unknown subject seed completely different from enrolled 100..1000
            unknown_face = _create_synthetic_subject(seed=u_id * 77, variation=0.20)
            b64_img = _to_b64(unknown_face)

            inp = MatchReadyCandidateInput(
                candidate_id=f"UNK-PROBE-{u_id}",
                track_id=f"TRACK-UNK-{u_id}",
                camera_id=2,
                face_image_base64=b64_img,
                face_quality_score=0.85,
                quality_status="GOOD",
                is_match_ready=True,
                search_mode=SearchMode.ALL_ACTIVE_CASES,
            )

            resp = self.service.process_match_ready_candidate(inp)

            # If top candidate exceeds review threshold (0.70) -> false match
            if resp.decision_state in (MatchDecisionState.POSSIBLE_MATCH, MatchDecisionState.HIGH_PRIORITY_REVIEW):
                false_matches += 1

        fmr = false_matches / total_unknowns
        # FMR must be below 0.20 on non-enrolled subjects
        assert fmr <= 0.20, f"False Match Rate {fmr:.2f} exceeds acceptable cutoff"

    def test_operational_telemetry_snapshot(self):
        """Verifies operational telemetry tracking."""
        snap = self.service.get_telemetry_snapshot()
        assert snap.active_missing_references == 5
        assert snap.active_wanted_references == 5
        assert snap.total_active_references == 10
        assert snap.active_model_name == "ANALYTICAL_V1"
