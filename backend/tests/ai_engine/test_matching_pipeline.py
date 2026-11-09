"""
Tests for Module 7 – End-to-End Candidate Matching Pipeline
============================================================
Verifies full pipeline flow from Module 6 match-ready observations,
dataset isolation (Missing vs. Wanted), multi-reference aggregation,
threshold gating, and PossibleMatchEvent generation.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.ai_engine.matching.embedding_service import FaceEmbeddingService
from app.ai_engine.matching.models.embedding_model import AnalyticalFaceEmbeddingModel
from app.ai_engine.matching.vector_search import VectorSearchIndex
from app.ai_engine.schemas.matching import (
    MatchDecisionState,
    MatchEventStatus,
    MatchReadyCandidateInput,
    ReferenceEmbeddingRecord,
    SearchMode,
)
from app.services.matching_service import MatchingService


def _generate_face(base_val: int = 120, eye_val: int = 30) -> np.ndarray:
    img = np.full((112, 112, 3), base_val, dtype=np.uint8)
    cv2.circle(img, (35, 40), 10, (eye_val, eye_val, eye_val), -1)
    cv2.circle(img, (75, 40), 10, (eye_val, eye_val, eye_val), -1)
    cv2.line(img, (56, 45), (56, 65), (50, 50, 50), 3)
    cv2.ellipse(img, (56, 85), (20, 8), 0, 0, 180, (20, 20, 20), 2)
    return img


@pytest.fixture
def service():
    """Sets up an isolated MatchingService instance with seeded reference index."""
    model = AnalyticalFaceEmbeddingModel()
    embedder = FaceEmbeddingService(model=model)
    index = VectorSearchIndex()
    srv = MatchingService(embedder=embedder, index=index)

    # Enroll Reference Case 1: MISSING (MP-2026-0001) with 2 reference photos
    face_mp1_a = _generate_face(base_val=100, eye_val=20)
    face_mp1_b = _generate_face(base_val=105, eye_val=22)
    vec_mp1_a = model.extract_embedding(face_mp1_a)
    vec_mp1_b = model.extract_embedding(face_mp1_b)

    rec_mp1_a = ReferenceEmbeddingRecord(
        image_id=1, case_id=1, case_number="MP-2026-0001", category="MISSING",
        department_id=1, model_name=model.model_name, model_version=model.model_version,
    )
    rec_mp1_b = ReferenceEmbeddingRecord(
        image_id=2, case_id=1, case_number="MP-2026-0001", category="MISSING",
        department_id=1, model_name=model.model_name, model_version=model.model_version,
    )
    index.add_embedding(rec_mp1_a, vec_mp1_a)
    index.add_embedding(rec_mp1_b, vec_mp1_b)

    # Enroll Reference Case 2: WANTED (WP-2026-0002) with 1 reference photo
    face_wp2 = _generate_face(base_val=180, eye_val=80)
    vec_wp2 = model.extract_embedding(face_wp2)
    rec_wp2 = ReferenceEmbeddingRecord(
        image_id=3, case_id=2, case_number="WP-2026-0002", category="WANTED",
        department_id=1, model_name=model.model_name, model_version=model.model_version,
    )
    index.add_embedding(rec_wp2, vec_wp2)

    return srv


class TestMatchingPipeline:

    def test_match_ready_candidate_matches_enrolled_reference(self, service):
        # Query face matching Case 1 (MP-2026-0001)
        query_face = _generate_face(base_val=100, eye_val=20)
        import base64
        _, enc = cv2.imencode(".jpg", query_face)
        b64 = base64.b64encode(enc.tobytes()).decode("utf-8")

        inp = MatchReadyCandidateInput(
            candidate_id="CAND-001",
            track_id="TRACK-001",
            camera_id=10,
            face_image_base64=b64,
            face_quality_score=0.88,
            quality_status="GOOD",
            face_detection_confidence=0.92,
            is_match_ready=True,
            search_mode=SearchMode.ALL_ACTIVE_CASES,
        )

        resp = service.process_match_ready_candidate(inp)

        assert resp.candidates_retrieved >= 1
        top_cand = resp.candidates[0]
        assert top_cand.case_number == "MP-2026-0001"
        assert top_cand.rank == 1
        assert top_cand.similarity_score > 0.85
        assert top_cand.decision_state in (
            MatchDecisionState.POSSIBLE_MATCH,
            MatchDecisionState.HIGH_PRIORITY_REVIEW,
        )
        assert len(resp.events_created) >= 1
        assert resp.events_created[0].case_number == "MP-2026-0001"
        assert resp.events_created[0].status == MatchEventStatus.PENDING_REVIEW

    def test_non_match_ready_candidate_gated_out(self, service):
        inp = MatchReadyCandidateInput(
            candidate_id="CAND-REJECTED",
            track_id="TRACK-999",
            camera_id=10,
            face_image_base64="dummy",
            face_quality_score=0.20,
            quality_status="POOR",
            is_match_ready=False,
        )

        resp = service.process_match_ready_candidate(inp)
        assert resp.candidates_retrieved == 0
        assert resp.decision_state == MatchDecisionState.NO_CANDIDATE
        assert len(resp.events_created) == 0

    def test_missing_dataset_isolation(self, service):
        # Query with face matching WANTED case (WP-2026-0002), but restrict search to MISSING
        query_face = _generate_face(base_val=180, eye_val=80)
        import base64
        _, enc = cv2.imencode(".jpg", query_face)
        b64 = base64.b64encode(enc.tobytes()).decode("utf-8")

        inp = MatchReadyCandidateInput(
            candidate_id="CAND-002",
            track_id="TRACK-002",
            camera_id=10,
            face_image_base64=b64,
            face_quality_score=0.85,
            quality_status="GOOD",
            is_match_ready=True,
            search_mode=SearchMode.MISSING,
        )

        resp = service.process_match_ready_candidate(inp)

        # MUST NOT return WANTED cases when search_mode is MISSING!
        for cand in resp.candidates:
            assert cand.category == "MISSING"
            assert cand.case_number != "WP-2026-0002"

    def test_wanted_dataset_isolation(self, service):
        # Query with face matching MISSING case, but restrict search to WANTED
        query_face = _generate_face(base_val=100, eye_val=20)
        import base64
        _, enc = cv2.imencode(".jpg", query_face)
        b64 = base64.b64encode(enc.tobytes()).decode("utf-8")

        inp = MatchReadyCandidateInput(
            candidate_id="CAND-003",
            track_id="TRACK-003",
            camera_id=10,
            face_image_base64=b64,
            face_quality_score=0.85,
            quality_status="GOOD",
            is_match_ready=True,
            search_mode=SearchMode.WANTED,
        )

        resp = service.process_match_ready_candidate(inp)

        # MUST NOT return MISSING cases when search_mode is WANTED!
        for cand in resp.candidates:
            assert cand.category == "WANTED"
            assert cand.case_number != "MP-2026-0001"

    def test_track_cooldown_anti_spamming(self, service):
        query_face = _generate_face(base_val=100, eye_val=20)
        import base64
        _, enc = cv2.imencode(".jpg", query_face)
        b64 = base64.b64encode(enc.tobytes()).decode("utf-8")

        inp = MatchReadyCandidateInput(
            candidate_id="CAND-FRAME-1",
            track_id="TRACK-BURST",
            camera_id=10,
            face_image_base64=b64,
            face_quality_score=0.88,
            quality_status="GOOD",
            is_match_ready=True,
        )

        # First observation emits event
        resp1 = service.process_match_ready_candidate(inp)
        assert len(resp1.events_created) == 1

        # Second observation within burst from the same track should NOT duplicate event
        inp2 = MatchReadyCandidateInput(
            candidate_id="CAND-FRAME-2",
            track_id="TRACK-BURST",
            camera_id=10,
            face_image_base64=b64,
            face_quality_score=0.90,
            quality_status="EXCELLENT",
            is_match_ready=True,
        )
        resp2 = service.process_match_ready_candidate(inp2)
        assert len(resp2.events_created) == 0  # debounced!
