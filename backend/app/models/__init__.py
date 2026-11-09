from app.models.case import Case
from app.models.department import Department
from app.models.user import User
from app.models.camera import Camera
from app.models.processing_event import ProcessingEvent  # noqa: F401
from app.models.face_quality_result import FaceQualityResultDB  # noqa: F401 – registers table with SQLAlchemy
from app.models.match_event import MatchEventDB  # noqa: F401 – registers match_events table
from app.models.face_embedding import FaceEmbeddingDB  # noqa: F401 – registers face_embeddings table
from app.models.review_event import ReviewEventDB, ReviewAuditLogDB, InvestigationTaskDB  # noqa: F401 – Module 8
from app.models.alert import (  # noqa: F401 – Module 9
    AlertDB,
    AlertRecipientDB,
    AlertNotificationDB,
    AlertAuditLogDB,
    AlertTimelineDB,
)
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
from app.models.system_config import SystemConfigDB, SystemConfigAuditDB  # noqa: F401 – Module 12
from app.models.backup import BackupRecordDB  # noqa: F401 – Module 12
