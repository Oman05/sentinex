"""
Tests for Module 6 – BestFrameSelector
========================================
Validates multi-frame track aggregation, ranking, best-observation selection,
track history management, and thread-safety.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from app.ai_engine.quality.best_frame_selector import BestFrameSelector
from app.ai_engine.schemas.quality import (
    FaceQualityResult,
    QualityClassification,
    RejectionReason,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _make_result(
    candidate_id: str,
    track_id: str = "track-A",
    quality_score: float = 0.70,
    is_match_ready: bool = True,
    status: QualityClassification = QualityClassification.GOOD,
    sharpness_score: float = 0.80,
    face_size_score: float = 0.85,
) -> FaceQualityResult:
    return FaceQualityResult(
        candidate_id=candidate_id,
        track_id=track_id,
        camera_id=1,
        timestamp=_ts(),
        sharpness_score=sharpness_score,
        brightness_score=0.75,
        contrast_score=0.70,
        face_size_score=face_size_score,
        pose_score=0.80,
        occlusion_score=0.10,
        detection_confidence=0.92,
        quality_score=quality_score,
        quality_status=status,
        is_match_ready=is_match_ready,
        reason="Test observation.",
        rejection_reason=RejectionReason.NONE if is_match_ready else RejectionReason.EXCESSIVE_BLUR,
        best_frame_reference=f"cam1-frame-{candidate_id}",
    )


def _poor_result(candidate_id: str, track_id: str = "track-A") -> FaceQualityResult:
    return _make_result(
        candidate_id=candidate_id,
        track_id=track_id,
        quality_score=0.30,
        is_match_ready=False,
        status=QualityClassification.POOR,
    )


def _excellent_result(candidate_id: str, track_id: str = "track-A") -> FaceQualityResult:
    return _make_result(
        candidate_id=candidate_id,
        track_id=track_id,
        quality_score=0.92,
        is_match_ready=True,
        status=QualityClassification.EXCELLENT,
        sharpness_score=0.95,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def selector():
    return BestFrameSelector(max_history=20)


# ---------------------------------------------------------------------------
# select_best – from a direct list of observations
# ---------------------------------------------------------------------------


class TestSelectBest:

    def test_empty_list_returns_none(self, selector):
        best, ranked, reason = selector.select_best([])
        assert best is None
        assert ranked == []
        assert isinstance(reason, str)

    def test_all_poor_returns_none_or_fallback(self, selector):
        observations = [_poor_result("c1"), _poor_result("c2")]
        best, ranked, reason = selector.select_best(observations)
        # No match-ready observations; best should be None
        assert best is None or not best.is_match_ready

    def test_best_observation_has_highest_score(self, selector):
        observations = [
            _make_result("c1", quality_score=0.60),
            _make_result("c2", quality_score=0.80),
            _make_result("c3", quality_score=0.70),
        ]
        best, ranked, reason = selector.select_best(observations)
        assert best is not None
        assert best.candidate_id == "c2"
        assert best.quality_score == pytest.approx(0.80)

    def test_ranked_list_is_sorted_descending(self, selector):
        observations = [
            _make_result("c1", quality_score=0.50),
            _make_result("c2", quality_score=0.90),
            _make_result("c3", quality_score=0.70),
        ]
        best, ranked, reason = selector.select_best(observations)
        scores = [o.quality_score for o in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_single_match_ready_selected(self, selector):
        observations = [
            _poor_result("c1"),
            _make_result("c2", quality_score=0.65),
            _poor_result("c3"),
        ]
        best, ranked, reason = selector.select_best(observations)
        assert best is not None
        assert best.candidate_id == "c2"

    def test_excellent_beats_good(self, selector):
        observations = [
            _make_result("good-frame", quality_score=0.75, status=QualityClassification.GOOD),
            _excellent_result("excellent-frame"),
        ]
        best, _, _ = selector.select_best(observations)
        assert best is not None
        assert best.candidate_id == "excellent-frame"

    def test_reason_is_nonempty_string(self, selector):
        observations = [_make_result("c1")]
        _, _, reason = selector.select_best(observations)
        assert isinstance(reason, str) and len(reason) > 0


# ---------------------------------------------------------------------------
# register_observation – per-track rolling history
# ---------------------------------------------------------------------------


class TestRegisterObservation:

    def test_first_registration_is_new_best(self, selector):
        obs = _make_result("c1", track_id="track-X")
        is_new_best, best = selector.register_observation(obs)
        assert is_new_best is True
        assert best.candidate_id == "c1"

    def test_higher_score_becomes_new_best(self, selector):
        selector.register_observation(_make_result("c1", quality_score=0.60, track_id="track-Y"))
        is_new_best, best = selector.register_observation(
            _make_result("c2", quality_score=0.85, track_id="track-Y")
        )
        assert is_new_best is True
        assert best.candidate_id == "c2"

    def test_lower_score_does_not_replace_best(self, selector):
        selector.register_observation(_make_result("c1", quality_score=0.90, track_id="track-Z"))
        is_new_best, best = selector.register_observation(
            _make_result("c2", quality_score=0.50, track_id="track-Z")
        )
        # Lower score should not become best
        assert best.quality_score == pytest.approx(0.90)

    def test_get_track_history_returns_all_observations(self, selector):
        track_id = "track-hist"
        for i in range(5):
            selector.register_observation(_make_result(f"c{i}", track_id=track_id, quality_score=0.5 + i * 0.05))
        history = selector.get_track_history(track_id)
        assert len(history) == 5

    def test_max_history_is_respected(self):
        small_selector = BestFrameSelector(max_history=3)
        track_id = "track-small"
        for i in range(10):
            small_selector.register_observation(_make_result(f"c{i}", track_id=track_id))
        history = small_selector.get_track_history(track_id)
        assert len(history) <= 3


# ---------------------------------------------------------------------------
# Track isolation
# ---------------------------------------------------------------------------


class TestTrackIsolation:

    def test_separate_tracks_do_not_interfere(self, selector):
        selector.register_observation(_make_result("a1", track_id="track-A", quality_score=0.90))
        selector.register_observation(_make_result("b1", track_id="track-B", quality_score=0.60))

        hist_a = selector.get_track_history("track-A")
        hist_b = selector.get_track_history("track-B")

        assert all(o.track_id == "track-A" for o in hist_a)
        assert all(o.track_id == "track-B" for o in hist_b)
        assert not any(o in hist_b for o in hist_a)

    def test_clear_track_removes_history(self, selector):
        selector.register_observation(_make_result("c1", track_id="track-clr"))
        selector.clear_track("track-clr")
        assert selector.get_track_history("track-clr") == []

    def test_reset_all_clears_all_tracks(self, selector):
        for tid in ["track-1", "track-2", "track-3"]:
            selector.register_observation(_make_result("cx", track_id=tid))
        selector.reset_all()
        for tid in ["track-1", "track-2", "track-3"]:
            assert selector.get_track_history(tid) == []

    def test_unknown_track_returns_empty(self, selector):
        assert selector.get_track_history("nonexistent-track") == []


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:

    def test_concurrent_registration_does_not_raise(self, selector):
        import threading

        errors = []

        def register_obs(i: int) -> None:
            try:
                selector.register_observation(
                    _make_result(f"c{i}", track_id="thread-track", quality_score=i * 0.01)
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_obs, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread-safety errors: {errors}"
        history = selector.get_track_history("thread-track")
        assert len(history) <= selector._max_history
