"""
Module 7 – Candidate Matching & Ranking Configuration
======================================================
All thresholds, similarity metrics, aggregation rules, ranking weights,
and feature extractor model settings are environment-driven via Pydantic
Settings to support experimental evaluation and tuning.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class CandidateMatchingSettings(BaseSettings):
    """Configuration settings for Module 7 candidate matching and ranking."""

    # -------------------------------------------------------------------------
    # Retrieval Limits
    # -------------------------------------------------------------------------
    TOP_K_CANDIDATES: int = 5
    """Maximum number of top-ranked candidates retrieved per search."""

    MAX_CANDIDATES_PER_EVENT: int = 5
    """Maximum number of candidate results attached to a possible match event."""

    # -------------------------------------------------------------------------
    # Similarity Metrics & Thresholds
    # -------------------------------------------------------------------------
    SIMILARITY_METRIC: str = "COSINE"
    """Distance / similarity metric: 'COSINE' or 'EUCLIDEAN'."""

    REVIEW_THRESHOLD: float = 0.45
    """Similarity score cutoff required to trigger POSSIBLE_MATCH."""

    HIGH_PRIORITY_THRESHOLD: float = 0.85
    """Similarity score cutoff required to trigger HIGH_PRIORITY_REVIEW."""

    LOW_SIMILARITY_CUTOFF: float = 0.40
    """Scores below this threshold are categorized as NO_CANDIDATE rather than LOW_SIMILARITY."""

    # -------------------------------------------------------------------------
    # Model Selection & Versioning
    # -------------------------------------------------------------------------
    EMBEDDING_MODEL: str = "OPENCV_SFACE"
    """Active feature extractor: 'ANALYTICAL_V1', 'OPENCV_SFACE', or 'FACENET_PYTORCH'."""

    EMBEDDING_MODEL_VERSION: str = "1.1.0"
    """Semantic version of the active face embedding model."""

    EMBEDDING_DIMENSION: int = 512
    """Feature vector dimensionality."""

    # -------------------------------------------------------------------------
    # Aggregation Strategies
    # -------------------------------------------------------------------------
    REFERENCE_AGGREGATION_METHOD: str = "MAXIMUM"
    """Case-level multiple reference aggregation: 'MAXIMUM', 'AVERAGE', or 'TOP_N'."""

    REFERENCE_TOP_N_COUNT: int = 3
    """Number of highest reference scores to average when using 'TOP_N'."""

    TRACK_AGGREGATION_METHOD: str = "BEST_OBSERVATION"
    """Temporal track evidence aggregation: 'BEST_OBSERVATION', 'AVERAGE', or 'EXPONENTIAL_DECAY'."""

    MAX_TRACK_OBSERVATIONS: int = 50
    """Maximum number of observation scores tracked per track ID in memory."""

    TRACK_COOLDOWN_SECONDS: float = 30.0
    """Cooldown duration before generating duplicate events for the same track and case."""

    # -------------------------------------------------------------------------
    # Candidate Ranking Weights (Must sum to 1.0)
    # -------------------------------------------------------------------------
    WEIGHT_SIMILARITY: float = 0.65
    """Weight assigned to raw / aggregated feature vector similarity."""

    WEIGHT_QUERY_QUALITY: float = 0.15
    """Weight assigned to Module 6 face quality score."""

    WEIGHT_REFERENCE_QUALITY: float = 0.10
    """Weight assigned to enrollment reference image quality score."""

    WEIGHT_MULTI_REF_BONUS: float = 0.10
    """Consistency bonus for matching across multiple reference images."""

    # -------------------------------------------------------------------------
    # Search Modes & Dataset Scopes
    # -------------------------------------------------------------------------
    SEARCH_MODE_DEFAULT: str = "ALL_ACTIVE_CASES"
    """Default candidate search scope: 'MISSING', 'WANTED', or 'ALL_ACTIVE_CASES'."""

    REQUIRE_ACTIVE_CASES_ONLY: bool = True
    """Whether to exclude non-ACTIVE or closed cases from the matching search index."""

    REQUIRE_ACTIVE_IMAGES_ONLY: bool = True
    """Whether to exclude deactivated reference images from the search index."""

    # -------------------------------------------------------------------------
    # Calibration Settings
    # -------------------------------------------------------------------------
    CALIBRATION_ENABLED: bool = False
    """Whether confidence calibration is scientifically validated and active."""

    CALIBRATION_SLOPE: float = 1.0
    """Slope parameter for linear/Platt probability scaling."""

    CALIBRATION_INTERCEPT: float = 0.0
    """Intercept parameter for linear/Platt probability scaling."""

    # -------------------------------------------------------------------------
    # Persistence & Behavior Flags
    # -------------------------------------------------------------------------
    PERSIST_MATCH_EVENTS: bool = True
    """Whether to record PossibleMatchEvents to the database match_events table."""

    PERSIST_EMBEDDINGS: bool = True
    """Whether to cache extracted feature vectors in face_embeddings table."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Module-level singleton
matching_settings = CandidateMatchingSettings()
