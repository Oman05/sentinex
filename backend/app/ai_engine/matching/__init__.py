"""
Module 7: Candidate Matching & Ranking Package
===============================================
Provides face feature extraction, reference dataset management,
vector similarity search, multiple-reference case aggregation,
temporal track-level evidence aggregation, non-biased candidate ranking,
and PossibleMatchEvent generation for Module 8 Human Verification.
"""

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
from app.ai_engine.matching.models.embedding_model import (
    AnalyticalFaceEmbeddingModel,
    BaseFaceEmbeddingModel,
    PyTorchFaceNetEmbeddingModel,
    get_embedding_model,
)
from app.ai_engine.matching.score_aggregator import (
    AggregatedCaseEvidence,
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

__all__ = [
    "AggregatedCaseEvidence",
    "AnalyticalFaceEmbeddingModel",
    "BaseFaceEmbeddingModel",
    "CandidateRanker",
    "FaceEmbeddingService",
    "MatchEventService",
    "PyTorchFaceNetEmbeddingModel",
    "ReferenceScoreAggregator",
    "SimilarityCalculator",
    "ThresholdManager",
    "TrackTemporalEvidenceAggregator",
    "VectorSearchIndex",
    "VectorSearchResult",
    "candidate_ranker",
    "embedding_service",
    "get_embedding_model",
    "match_event_service",
    "reference_score_aggregator",
    "similarity_calculator",
    "threshold_manager",
    "track_evidence_aggregator",
    "vector_search_index",
]
