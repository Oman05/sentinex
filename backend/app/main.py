import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.ai_processing import router as ai_processing_router
from app.api.cameras import router as cameras_router
from app.api.cases import router as cases_router
from app.api.datasets import dataset_router
from app.api.face_quality import router as face_quality_router
from app.api.matching import router as matching_router
from app.api.review import router as review_router
from app.api.alert import router as alert_router, internal_router as internal_alert_router
from app.api.evidence import router as evidence_router, audit_router
from app.api.analytics import router as analytics_router, eval_router, model_router
from app.api.images import image_router, router as images_router
from app.api.routes.auth import router as auth_router
from app.api.routes.permissions import router as permissions_router
from app.database.session import init_db
from app.models.camera import Camera  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.face_quality_result import FaceQualityResultDB  # noqa: F401
from app.models.match_event import MatchEventDB  # noqa: F401
from app.models.face_embedding import FaceEmbeddingDB  # noqa: F401
from app.models.review_event import ReviewEventDB, ReviewAuditLogDB, InvestigationTaskDB  # noqa: F401
from app.models.alert import AlertDB, AlertRecipientDB, AlertNotificationDB, AlertAuditLogDB, AlertTimelineDB  # noqa: F401
from app.models.evidence import (  # noqa: F401 – Module 10
    EvidenceRetentionPolicyDB,
    EvidenceItemDB,
    EvidenceVersionDB,
    EvidenceRelationshipDB,
    EvidenceAccessLogDB,
    EvidenceExportDB,
    SystemAuditLogDB,
)
from app.models.analytics import (  # noqa: F401 – Module 11
    ModelRegistryDB,
    DatasetRegistryDB,
    EvaluationRunDB,
    EvaluationResultDB,
    DriftEventDB,
    AnalyticsAlertDB,
    SystemMetricsSnapshotDB,
)
from app.models.processing_event import ProcessingEvent  # noqa: F401
from app.services.quality_service import quality_service
from app.services.stream_manager import stream_manager
from app.ai_engine.pipeline.processing_pipeline import video_pipeline


from app.api.health import router as health_router
from app.services.config_service import config_service
from app.database.session import SessionLocal


from app.ai_engine.schemas.observations import CandidateObservation
from app.services.matching_service import matching_service

logger = logging.getLogger(__name__)


def handle_live_candidate(candidate: CandidateObservation) -> None:
    """
    Complete end-to-end perception to verification dispatcher:
    CandidateObservation
    -> Face Quality Assessment (Module 6)
    -> Face Feature Embedding Generation & Search Registered Reference Embeddings (Module 7)
    -> Candidate Match Evaluation & Ranking
    -> Possible Match Event & Review Queue Ingestion (Module 8)
    """
    try:
        # 1. Quality assessment
        quality_res = quality_service.assess_candidate_observation(candidate)
        if not quality_res or (not quality_res.is_match_ready and quality_res.quality_score < 0.35):
            return

        # 2. Forward match-ready observation to candidate matching engine
        from app.ai_engine.schemas.matching import MatchReadyCandidateInput

        match_input = MatchReadyCandidateInput(
            candidate_id=candidate.candidate_id,
            track_id=candidate.track_id,
            camera_id=candidate.camera_id,
            timestamp=candidate.timestamp,
            face_image_base64=candidate.face_crop_base64,
            face_quality_score=quality_res.quality_score,
            quality_status=quality_res.quality_status.value,
            face_detection_confidence=quality_res.detection_confidence,
            camera_location=candidate.location,
            department_id=None,
            is_match_ready=True,
        )
        res = matching_service.process_match_ready_candidate(match_input)
        if res.candidates:
            top = res.candidates[0]
            logger.info(
                "[LivePipeline] MATCH CANDIDATE: case=%s cat=%s score=%.3f state=%s",
                top.case_number, top.category, top.final_score, top.decision_state,
            )
    except Exception as exc:
        logger.error("[LivePipeline] Candidate processing error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        config_service.initialize_defaults(db)
        loaded = matching_service.sync_index_from_database(db)
        logger.info("[Lifespan] Loaded %d reference embeddings into matching index", loaded)
    finally:
        db.close()

    video_pipeline.add_candidate_handler(handle_live_candidate)
    try:
        yield
    finally:
        video_pipeline.remove_candidate_handler(handle_live_candidate)
        await stream_manager.stop_all()
        await video_pipeline.stop_all()



app = FastAPI(
    title="SENTINEX - AI-Based Missing and Wanted Person Detection & Alert System",
    description=(
        "Core Backend Platform:\n"
        "- Module 1: Authentication & Role Management (JWT + RBAC)\n"
        "- Module 2: Case Management (Missing & Wanted Cases)\n"
        "- Module 3: Reference Image Enrollment & Dataset Management\n"
        "- Module 4: Live CCTV Streaming & Monitoring\n"
        "- Module 5: AI Video Processing (Person & Face Detection, Tracking)\n"
        "- Module 6: Face Quality Assessment (Sharpness, Lighting, Resolution, Pose, Occlusion)\n"
        "- Module 7: Candidate Matching & Ranking (Feature Embeddings, Vector Search, Case Aggregation)\n"
        "- Module 8: Human Verification & Investigation Dashboard\n"
        "- Module 9: Alert & Department Notification System\n"
        "- Module 10: Evidence Management, Audit Trail & Chain of Custody\n"
        "- Module 11: Analytics, Evaluation & Model Monitoring"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

from app.middleware.rate_limiter import RateLimiterMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware, max_requests=60, window_seconds=60)

# API routes prefixed with /api
app.include_router(auth_router, prefix="/api")
app.include_router(permissions_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(cases_router, prefix="/api")
app.include_router(cameras_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(image_router, prefix="/api")
app.include_router(dataset_router, prefix="/api")
app.include_router(ai_processing_router, prefix="/api")
app.include_router(face_quality_router, prefix="/api")
app.include_router(matching_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(alert_router, prefix="/api")
app.include_router(internal_alert_router, prefix="/api")
app.include_router(evidence_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")  # Module 11
app.include_router(health_router, prefix="/api")      # Module 12 Health
app.include_router(eval_router, prefix="/api")        # Module 11
app.include_router(model_router, prefix="/api")       # Module 11

# Also mount routers at root for direct path matching
app.include_router(admin_router, include_in_schema=False)
app.include_router(health_router, include_in_schema=False)
app.include_router(cases_router, include_in_schema=False)
app.include_router(cameras_router, include_in_schema=False)
app.include_router(images_router, include_in_schema=False)
app.include_router(image_router, include_in_schema=False)
app.include_router(dataset_router, include_in_schema=False)
app.include_router(ai_processing_router, include_in_schema=False)
app.include_router(face_quality_router, include_in_schema=False)
app.include_router(matching_router, include_in_schema=False)
app.include_router(review_router, include_in_schema=False)
app.include_router(alert_router, include_in_schema=False)
app.include_router(internal_alert_router, include_in_schema=False)
app.include_router(evidence_router, include_in_schema=False)
app.include_router(audit_router, include_in_schema=False)
app.include_router(analytics_router, include_in_schema=False)  # Module 11
app.include_router(eval_router, include_in_schema=False)       # Module 11
app.include_router(model_router, include_in_schema=False)      # Module 11

# Frontend convenience aliases for reviewApi.ts and LiveCameraDemo
from app.api.review import (
    get_dashboard_stats,
    list_review_events,
    get_review_event,
    get_notifications_route,
    list_tasks,
    create_task,
)

frontend_compat_router = APIRouter(prefix="/api", include_in_schema=False)
frontend_compat_router.add_api_route("/dashboard/stats", get_dashboard_stats, methods=["GET"])
frontend_compat_router.add_api_route("/reviews", list_review_events, methods=["GET"])
frontend_compat_router.add_api_route("/reviews/{event_id}", get_review_event, methods=["GET"])
frontend_compat_router.add_api_route("/notifications", get_notifications_route, methods=["GET"])
frontend_compat_router.add_api_route("/tasks", list_tasks, methods=["GET"])
frontend_compat_router.add_api_route("/tasks", create_task, methods=["POST"])
app.include_router(frontend_compat_router)


