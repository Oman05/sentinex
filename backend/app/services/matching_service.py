"""
Module 7 – Matching Service (High-Level Orchestrator)
=====================================================
Orchestrates candidate retrieval, reference aggregation, ranking,
threshold evaluation, and event dispatch for Module 7.
Integrates directly with Module 6 (Quality Assessor) and Module 8 (Verification).

AI Safety Invariant:
--------------------
Outputs 'POSSIBLE MATCH — REQUIRES AUTHORIZED HUMAN VERIFICATION'.
Never declares an identity confirmed.
Distinguishes detection confidence, face quality, similarity, and ranking scores.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Sequence

import numpy as np
from sqlalchemy.orm import Session

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.matching.candidate_ranker import (
    CandidateRanker,
    candidate_ranker,
)
from app.ai_engine.matching.embedding_service import (
    FaceEmbeddingService,
    embedding_service,
)
from app.ai_engine.matching.match_event_service import (
    MatchEventService,
    match_event_service,
)
from app.ai_engine.matching.score_aggregator import (
    ReferenceScoreAggregator,
    TrackTemporalEvidenceAggregator,
    reference_score_aggregator,
    track_evidence_aggregator,
)
from app.ai_engine.matching.similarity import (
    SimilarityCalculator,
    similarity_calculator,
)
from app.ai_engine.matching.threshold_manager import (
    ThresholdManager,
    threshold_manager,
)
from app.ai_engine.matching.vector_search import (
    VectorSearchIndex,
    VectorSearchResult,
    vector_search_index,
)
from app.ai_engine.schemas.matching import (
    CandidateMatchResult,
    CandidateSearchResponse,
    DirectQueryFaceRequest,
    MatchDecisionState,
    MatchEventStatus,
    MatchingTelemetryResponse,
    MatchReadyCandidateInput,
    PossibleMatchEvent,
    ReferenceAggregationMethod,
    ReferenceEmbeddingRecord,
    ReindexResponse,
    SearchMode,
    SimilarityMetric,
)
from app.database.session import SessionLocal
from app.models.case import Case, CaseStatus
from app.models.reference_image import ReferenceImage

logger = logging.getLogger(__name__)


class _MatchingTelemetryTracker:
    """Thread-safe performance and telemetry accumulator."""

    def __init__(self, index: VectorSearchIndex | None = None) -> None:
        self._lock = threading.Lock()
        self.index = index
        self.queries_processed: int = 0
        self.candidates_retrieved: int = 0
        self.possible_matches_created: int = 0
        self.high_priority_matches_created: int = 0
        self.no_candidate_results: int = 0
        self.total_search_latency_s: float = 0.0
        self.total_embedding_latency_s: float = 0.0
        self.total_vector_search_latency_s: float = 0.0

    def record_query(
        self,
        candidates_count: int,
        events_created: list[PossibleMatchEvent],
        decision_state: MatchDecisionState,
        search_latency_s: float,
        embedding_latency_s: float,
        vector_search_latency_s: float,
    ) -> None:
        with self._lock:
            self.queries_processed += 1
            self.candidates_retrieved += candidates_count
            self.total_search_latency_s += search_latency_s
            self.total_embedding_latency_s += embedding_latency_s
            self.total_vector_search_latency_s += vector_search_latency_s

            if decision_state == MatchDecisionState.NO_CANDIDATE:
                self.no_candidate_results += 1

            for ev in events_created:
                if ev.decision_state == MatchDecisionState.HIGH_PRIORITY_REVIEW:
                    self.high_priority_matches_created += 1
                elif ev.decision_state == MatchDecisionState.POSSIBLE_MATCH:
                    self.possible_matches_created += 1

    def snapshot(self, index: VectorSearchIndex | None = None) -> MatchingTelemetryResponse:
        idx = index or self.index or vector_search_index
        with self._lock:
            q = max(1, self.queries_processed)
            avg_search = (self.total_search_latency_s / q) * 1000.0
            avg_emb = (self.total_embedding_latency_s / q) * 1000.0
            avg_vec = (self.total_vector_search_latency_s / q) * 1000.0

            return MatchingTelemetryResponse(
                queries_processed=self.queries_processed,
                candidates_retrieved=self.candidates_retrieved,
                possible_matches_created=self.possible_matches_created,
                high_priority_matches_created=self.high_priority_matches_created,
                no_candidate_results=self.no_candidate_results,
                average_search_latency_ms=round(avg_search, 2),
                embedding_generation_latency_ms=round(avg_emb, 2),
                vector_search_latency_ms=round(avg_vec, 2),
                active_missing_references=idx.count_active(SearchMode.MISSING),
                active_wanted_references=idx.count_active(SearchMode.WANTED),
                total_active_references=idx.count_active(SearchMode.ALL_ACTIVE_CASES),
                active_model_name=matching_settings.EMBEDDING_MODEL,
                active_model_version=matching_settings.EMBEDDING_MODEL_VERSION,
            )


class MatchingService:
    """
    Core candidate matching engine coordinating perception inputs,
    vector database search, case evidence aggregation, and alert creation.
    """

    def __init__(
        self,
        embedder: FaceEmbeddingService | None = None,
        index: VectorSearchIndex | None = None,
        aggregator: ReferenceScoreAggregator | None = None,
        temporal_tracker: TrackTemporalEvidenceAggregator | None = None,
        ranker: CandidateRanker | None = None,
        thresholds: ThresholdManager | None = None,
        event_mgr: MatchEventService | None = None,
    ) -> None:
        self.embedder = embedder or embedding_service
        self.index = index or vector_search_index
        self.aggregator = aggregator or reference_score_aggregator
        self.temporal_tracker = temporal_tracker or track_evidence_aggregator
        self.ranker = ranker or candidate_ranker
        if thresholds is not None:
            self.thresholds = thresholds
        elif getattr(self.embedder, "model_name", "").upper() in {"ANALYTICAL_V1", "ANALYTICAL"}:
            self.thresholds = ThresholdManager(review_threshold=0.70, high_priority_threshold=0.85)
        else:
            self.thresholds = threshold_manager
        self.event_mgr = event_mgr or match_event_service
        self.telemetry = _MatchingTelemetryTracker(index=self.index)

    def process_match_ready_candidate(
        self,
        candidate_input: MatchReadyCandidateInput,
        db: Session | None = None,
    ) -> CandidateSearchResponse:
        """
        Receives a match-ready face observation from Module 6 and executes
        the complete Candidate Matching & Ranking pipeline.
        """
        start_time = time.perf_counter()

        # Gate Check: Only observations where is_match_ready=True enter matching
        if not candidate_input.is_match_ready:
            logger.info(
                "[MatchingService] Candidate %s rejected: is_match_ready=False",
                candidate_input.candidate_id,
            )
            return CandidateSearchResponse(
                query_candidate_id=candidate_input.candidate_id,
                search_mode=candidate_input.search_mode or SearchMode(matching_settings.SEARCH_MODE_DEFAULT),
                similarity_metric=SimilarityMetric(matching_settings.SIMILARITY_METRIC),
                reference_aggregation_method=ReferenceAggregationMethod(matching_settings.REFERENCE_AGGREGATION_METHOD),
                candidates_retrieved=0,
                decision_state=MatchDecisionState.NO_CANDIDATE,
                candidates=[],
                events_created=[],
                latency_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            )

        # 1. Feature / Embedding Generation
        img_source = candidate_input.face_image_base64 or candidate_input.face_image_reference
        emb_start = time.perf_counter()
        query_vec = self.embedder.extract_face_embedding(img_source)
        emb_latency = time.perf_counter() - emb_start

        if query_vec is None:
            logger.warning(
                "[MatchingService] Could not generate embedding for candidate %s",
                candidate_input.candidate_id,
            )
            return CandidateSearchResponse(
                query_candidate_id=candidate_input.candidate_id,
                search_mode=candidate_input.search_mode or SearchMode(matching_settings.SEARCH_MODE_DEFAULT),
                similarity_metric=SimilarityMetric(matching_settings.SIMILARITY_METRIC),
                reference_aggregation_method=ReferenceAggregationMethod(matching_settings.REFERENCE_AGGREGATION_METHOD),
                candidates_retrieved=0,
                decision_state=MatchDecisionState.NO_CANDIDATE,
                candidates=[],
                events_created=[],
                latency_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            )

        # 2. Vector Similarity Search
        mode = candidate_input.search_mode or SearchMode(matching_settings.SEARCH_MODE_DEFAULT)
        vec_start = time.perf_counter()
        # Retrieve extra raw vectors to allow aggregation per case
        raw_matches = self.index.search(
            query_vector=query_vec,
            top_k=max(20, matching_settings.TOP_K_CANDIDATES * 4),
            mode=mode,
            department_id=candidate_input.department_id,
            metric=matching_settings.SIMILARITY_METRIC,
        )
        vec_latency = time.perf_counter() - vec_start

        # 3. Group reference hits by Case ID
        case_map: dict[int, list[tuple[int, float]]] = {}
        case_info_map: dict[int, tuple[str, str, int]] = {}  # case_id -> (case_number, category, department_id)

        for match in raw_matches:
            cid = match.record.case_id
            if cid not in case_map:
                case_map[cid] = []
                case_info_map[cid] = (
                    match.record.case_number,
                    match.record.category,
                    match.record.department_id,
                )
            case_map[cid].append((match.record.image_id, match.similarity_score))

        # 4. Multiple Reference Image Evidence Aggregation at Case Level
        case_evidences = []
        for cid, ref_scores in case_map.items():
            cnum, ccat, cdept = case_info_map[cid]
            evidence = self.aggregator.aggregate_case_references(
                case_id=cid,
                case_number=cnum,
                category=ccat,
                department_id=cdept,
                reference_evaluations=ref_scores,
            )
            # 5. Temporal Track Aggregation
            track_smoothed_score = self.temporal_tracker.register_observation(
                track_id=candidate_input.track_id,
                case_id=cid,
                similarity_score=evidence.aggregated_similarity,
            )
            # Update aggregated similarity with temporal track evidence if multi-frame
            evidence.aggregated_similarity = track_smoothed_score
            case_evidences.append(evidence)

        # 6. Candidate Ranking
        ranked_candidates = self.ranker.rank_candidates(
            case_evidences=case_evidences,
            query_quality_score=candidate_input.face_quality_score,
            decision_evaluator_fn=self.thresholds.evaluate_candidate,
            top_k=matching_settings.TOP_K_CANDIDATES,
        )

        # 7. Evaluate Policy Cutoffs & Dispatch PossibleMatchEvents
        overall_state = MatchDecisionState.NO_CANDIDATE
        events_created: list[PossibleMatchEvent] = []

        if ranked_candidates:
            # Top candidate sets overall decision state
            overall_state = ranked_candidates[0].decision_state

            # Emit events for any candidate achieving POSSIBLE_MATCH or HIGH_PRIORITY_REVIEW
            for cand in ranked_candidates:
                if cand.decision_state in {
                    MatchDecisionState.POSSIBLE_MATCH,
                    MatchDecisionState.HIGH_PRIORITY_REVIEW,
                }:
                    event = self.event_mgr.create_possible_match_event(
                        candidate_id=candidate_input.candidate_id,
                        track_id=candidate_input.track_id,
                        camera_id=candidate_input.camera_id,
                        timestamp=candidate_input.timestamp,
                        matched_candidate=cand,
                        query_quality_score=candidate_input.face_quality_score,
                        camera_location=candidate_input.camera_location,
                        model_name=self.embedder.model_name,
                        model_version=self.embedder.model_version,
                        db=db,
                    )
                    if event is not None:
                        events_created.append(event)

        elapsed_total = time.perf_counter() - start_time

        # Update Telemetry
        self.telemetry.record_query(
            candidates_count=len(ranked_candidates),
            events_created=events_created,
            decision_state=overall_state,
            search_latency_s=elapsed_total,
            embedding_latency_s=emb_latency,
            vector_search_latency_s=vec_latency,
        )

        return CandidateSearchResponse(
            query_candidate_id=candidate_input.candidate_id,
            search_mode=mode,
            similarity_metric=SimilarityMetric(matching_settings.SIMILARITY_METRIC),
            reference_aggregation_method=self.aggregator.method,
            candidates_retrieved=len(ranked_candidates),
            decision_state=overall_state,
            candidates=ranked_candidates,
            events_created=events_created,
            latency_ms=round(elapsed_total * 1000.0, 2),
        )

    def search_query_face(
        self,
        request: DirectQueryFaceRequest,
        db: Session | None = None,
    ) -> CandidateSearchResponse:
        """Executes candidate search from direct face image input."""
        fake_input = MatchReadyCandidateInput(
            candidate_id=f"QUERY-{int(time.time() * 1000)}",
            track_id="MANUAL-QUERY-00",
            camera_id=0,
            timestamp=datetime.now(timezone.utc),
            face_image_reference=request.face_image_reference,
            face_image_base64=request.face_image_base64,
            face_quality_score=0.85,
            quality_status="GOOD",
            face_detection_confidence=0.95,
            camera_location="MANUAL_SEARCH_CONSOLE",
            department_id=request.department_id,
            is_match_ready=True,
            search_mode=request.search_mode,
        )
        return self.process_match_ready_candidate(fake_input, db=db)

    def reindex_reference_images(self, db: Session) -> ReindexResponse:
        """Trigger re-indexing of all active reference images into the vector index."""
        return self.embedder.reindex_all_reference_images(db=db)

    def sync_index_from_database(self, db: Session) -> int:
        """
        Initializes the in-memory search index on system startup from
        stored face_embeddings or active reference images.
        """
        from app.models.face_embedding import FaceEmbeddingDB

        # Try fast load from persisted embeddings
        embeddings = db.query(FaceEmbeddingDB).filter(FaceEmbeddingDB.is_active == True).all()
        if embeddings:
            count = 0
            for emb in embeddings:
                # Query associated reference image and case
                ref_img = (
                    db.query(ReferenceImage)
                    .filter(ReferenceImage.id == emb.reference_image_id)
                    .first()
                )
                case = db.query(Case).filter(Case.id == emb.case_id).first()
                if ref_img and case and case.is_active and ref_img.is_active:
                    vec = np.frombuffer(emb.vector_bytes, dtype=np.float32)
                    rec = ReferenceEmbeddingRecord(
                        embedding_id=emb.embedding_reference,
                        image_id=ref_img.id,
                        case_id=case.id,
                        case_number=case.case_number,
                        category=case.category,
                        department_id=case.department_id,
                        model_name=emb.model_name,
                        model_version=emb.model_version,
                        embedding_dim=emb.embedding_dim,
                        is_active=True,
                    )
                    self.index.add_embedding(rec, vec)
                    count += 1
            logger.info("[MatchingService] Initialized %d embeddings from database cache", count)
            return count

        # If no cached embeddings, re-index from reference images
        reindex_res = self.reindex_reference_images(db=db)
        return reindex_res.embeddings_generated

    def get_telemetry_snapshot(self) -> MatchingTelemetryResponse:
        """Returns live telemetry snapshot."""
        snap = self.telemetry.snapshot(index=self.index)
        snap.active_model_name = self.embedder.model_name
        snap.active_model_version = self.embedder.model_version
        return snap


# Module-level singleton
matching_service = MatchingService()
