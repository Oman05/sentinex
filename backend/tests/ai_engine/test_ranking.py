"""
Tests for Module 7 – Candidate Ranking & Evidence Aggregation
=============================================================
Verifies reference aggregation (MAXIMUM, AVERAGE, TOP_N), temporal track
evidence, non-biased candidate ranking, and sort ordering.
"""

from __future__ import annotations

import pytest

from app.ai_engine.matching.candidate_ranker import CandidateRanker
from app.ai_engine.matching.score_aggregator import (
    AggregatedCaseEvidence,
    ReferenceScoreAggregator,
    TrackTemporalEvidenceAggregator,
)
from app.ai_engine.schemas.matching import (
    CalibrationStatus,
    MatchDecisionState,
    ReferenceAggregationMethod,
    TrackAggregationMethod,
)


class TestReferenceScoreAggregator:

    def test_maximum_aggregation(self):
        agg = ReferenceScoreAggregator(method=ReferenceAggregationMethod.MAXIMUM)
        refs = [(101, 0.65), (102, 0.92), (103, 0.78)]
        res = agg.aggregate_case_references(
            case_id=1,
            case_number="MP-2026-0001",
            category="MISSING",
            department_id=1,
            reference_evaluations=refs,
        )
        assert res.aggregated_similarity == 0.92
        assert res.best_reference_image_id == 102
        assert res.reference_count == 3

    def test_average_aggregation(self):
        agg = ReferenceScoreAggregator(method=ReferenceAggregationMethod.AVERAGE)
        refs = [(101, 0.60), (102, 0.80), (103, 0.70)]
        res = agg.aggregate_case_references(
            case_id=1,
            case_number="MP-2026-0001",
            category="MISSING",
            department_id=1,
            reference_evaluations=refs,
        )
        assert pytest.approx(res.aggregated_similarity, abs=1e-3) == 0.70
        assert res.best_reference_image_id == 102

    def test_top_n_aggregation(self):
        agg = ReferenceScoreAggregator(method=ReferenceAggregationMethod.TOP_N, top_n=2)
        # Top 2 scores: 0.90 and 0.80 -> average = 0.85
        refs = [(101, 0.50), (102, 0.80), (103, 0.90), (104, 0.40)]
        res = agg.aggregate_case_references(
            case_id=1,
            case_number="MP-2026-0001",
            category="MISSING",
            department_id=1,
            reference_evaluations=refs,
        )
        assert pytest.approx(res.aggregated_similarity, abs=1e-3) == 0.85

    def test_empty_reference_evaluations(self):
        agg = ReferenceScoreAggregator()
        res = agg.aggregate_case_references(
            case_id=1,
            case_number="MP-2026-0001",
            category="MISSING",
            department_id=1,
            reference_evaluations=[],
        )
        assert res.aggregated_similarity == 0.0
        assert res.best_reference_image_id is None
        assert res.reference_count == 0


class TestTrackTemporalEvidenceAggregator:

    def test_track_best_observation(self):
        tracker = TrackTemporalEvidenceAggregator(method=TrackAggregationMethod.BEST_OBSERVATION)
        tracker.register_observation("TRACK-1", case_id=10, similarity_score=0.71)
        tracker.register_observation("TRACK-1", case_id=10, similarity_score=0.88)
        tracker.register_observation("TRACK-1", case_id=10, similarity_score=0.75)

        score = tracker.get_aggregated_score("TRACK-1", case_id=10)
        assert score == 0.88
        assert tracker.get_observation_count("TRACK-1", case_id=10) == 3

    def test_track_average_observation(self):
        tracker = TrackTemporalEvidenceAggregator(method=TrackAggregationMethod.AVERAGE)
        tracker.register_observation("TRACK-1", case_id=10, similarity_score=0.70)
        tracker.register_observation("TRACK-1", case_id=10, similarity_score=0.80)
        tracker.register_observation("TRACK-1", case_id=10, similarity_score=0.90)

        score = tracker.get_aggregated_score("TRACK-1", case_id=10)
        assert pytest.approx(score, abs=1e-3) == 0.80

    def test_track_isolation_and_cleanup(self):
        tracker = TrackTemporalEvidenceAggregator()
        tracker.register_observation("TRACK-A", case_id=1, similarity_score=0.85)
        tracker.register_observation("TRACK-B", case_id=1, similarity_score=0.60)

        assert tracker.get_aggregated_score("TRACK-A", 1) == 0.85
        assert tracker.get_aggregated_score("TRACK-B", 1) == 0.60

        tracker.clear_track("TRACK-A")
        assert tracker.get_aggregated_score("TRACK-A", 1) == 0.0
        assert tracker.get_aggregated_score("TRACK-B", 1) == 0.60


class TestCandidateRanker:

    @pytest.fixture
    def ranker(self):
        return CandidateRanker(
            weight_similarity=0.60,
            weight_query_quality=0.20,
            weight_reference_quality=0.10,
            weight_multi_ref_bonus=0.10,
        )

    def test_ranking_score_bounded_zero_to_one(self, ranker):
        score_min = ranker.compute_ranking_score(0.0, 0.0, 0.0, 1)
        score_max = ranker.compute_ranking_score(1.0, 1.0, 1.0, 3)
        assert 0.0 <= score_min <= 1.0
        assert 0.0 <= score_max <= 1.0
        assert score_min < score_max

    def test_candidates_sorted_descending(self, ranker):
        ev1 = AggregatedCaseEvidence(
            case_id=1, case_number="MP-001", category="MISSING", department_id=1,
            aggregated_similarity=0.70, best_similarity=0.70, best_reference_image_id=10,
            reference_count=1, aggregation_method=ReferenceAggregationMethod.MAXIMUM,
            all_reference_scores=[(10, 0.70)],
        )
        ev2 = AggregatedCaseEvidence(
            case_id=2, case_number="WP-002", category="WANTED", department_id=1,
            aggregated_similarity=0.92, best_similarity=0.92, best_reference_image_id=20,
            reference_count=3, aggregation_method=ReferenceAggregationMethod.MAXIMUM,
            all_reference_scores=[(20, 0.92)],
        )

        def dummy_eval(sim):
            return MatchDecisionState.POSSIBLE_MATCH, None, CalibrationStatus.NOT_CALIBRATED

        ranked = ranker.rank_candidates([ev1, ev2], query_quality_score=0.85, decision_evaluator_fn=dummy_eval)
        assert len(ranked) == 2
        # Case 2 with 0.92 similarity should be ranked #1
        assert ranked[0].case_number == "WP-002"
        assert ranked[0].rank == 1
        assert ranked[1].case_number == "MP-001"
        assert ranked[1].rank == 2

    def test_multi_reference_evidence_bonus(self, ranker):
        score_single = ranker.compute_ranking_score(similarity_score=0.80, query_quality_score=0.80, matched_reference_count=1)
        score_multi = ranker.compute_ranking_score(similarity_score=0.80, query_quality_score=0.80, matched_reference_count=3)
        assert score_multi > score_single
