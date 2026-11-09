from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfigDB, SystemConfigAuditDB

DEFAULT_CONFIGS = [
    # AI Configuration
    {
        "category": "AI",
        "key": "PERSON_DETECTION_THRESHOLD",
        "value": "0.45",
        "value_type": "float",
        "description": "Confidence threshold for YOLO person detector",
    },
    {
        "category": "AI",
        "key": "FACE_DETECTION_THRESHOLD",
        "value": "0.60",
        "value_type": "float",
        "description": "Confidence threshold for MTCNN face detector",
    },
    {
        "category": "AI",
        "key": "MIN_FACE_SIZE",
        "value": "32",
        "value_type": "int",
        "description": "Minimum face bounding box width/height in pixels",
    },
    {
        "category": "AI",
        "key": "MIN_QUALITY_SCORE",
        "value": "0.50",
        "value_type": "float",
        "description": "Composite face quality gate cutoff threshold",
    },
    {
        "category": "AI",
        "key": "MATCH_TOP_K",
        "value": "5",
        "value_type": "int",
        "description": "Maximum number of candidate matches retrieved per query",
    },
    {
        "category": "AI",
        "key": "MATCH_SIMILARITY_THRESHOLD",
        "value": "0.70",
        "value_type": "float",
        "description": "Cosine similarity cutoff for proposing candidate matches",
    },
    {
        "category": "AI",
        "key": "TRACK_TIMEOUT",
        "value": "30.0",
        "value_type": "float",
        "description": "Maximum idle time in seconds before discarding a tracking state",
    },
    # Processing Configuration
    {
        "category": "PROCESSING",
        "key": "FRAME_SAMPLING_INTERVAL",
        "value": "1.0",
        "value_type": "float",
        "description": "Time interval in seconds between sampled stream frames",
    },
    {
        "category": "PROCESSING",
        "key": "MAX_CAMERAS_PER_WORKER",
        "value": "4",
        "value_type": "int",
        "description": "Maximum concurrent camera streams assigned per processing worker",
    },
    {
        "category": "PROCESSING",
        "key": "MAX_QUEUE_SIZE",
        "value": "16",
        "value_type": "int",
        "description": "Bounded queue capacity for video frames before dropping",
    },
    {
        "category": "PROCESSING",
        "key": "PROCESSING_TIMEOUT",
        "value": "10.0",
        "value_type": "float",
        "description": "Inference deadline timeout per frame in seconds",
    },
    # Alerts Configuration
    {
        "category": "ALERTS",
        "key": "ALERT_ESCALATION_ENABLED",
        "value": "true",
        "value_type": "bool",
        "description": "Whether unacknowledged alerts escalate to central command",
    },
    {
        "category": "ALERTS",
        "key": "ALERT_RETRY_COUNT",
        "value": "3",
        "value_type": "int",
        "description": "Maximum transmission attempts per notification channel",
    },
    {
        "category": "ALERTS",
        "key": "ALERT_TIMEOUT",
        "value": "15",
        "value_type": "int",
        "description": "Minutes allowed before an alert is considered unacknowledged",
    },
    {
        "category": "ALERTS",
        "key": "DUPLICATE_ALERT_WINDOW",
        "value": "60",
        "value_type": "int",
        "description": "Deduplication window in minutes for the same person & camera",
    },
    # Storage Configuration
    {
        "category": "STORAGE",
        "key": "MAX_UPLOAD_SIZE",
        "value": "10485760",
        "value_type": "int",
        "description": "Maximum upload file size in bytes (10MB)",
    },
    {
        "category": "STORAGE",
        "key": "EVIDENCE_RETENTION_PERIOD",
        "value": "365",
        "value_type": "int",
        "description": "Default evidence retention period in days",
    },
    {
        "category": "STORAGE",
        "key": "MAX_VIDEO_SIZE",
        "value": "2147483648",
        "value_type": "int",
        "description": "Maximum video clip storage size in bytes (2GB)",
    },
    # Security Configuration
    {
        "category": "SECURITY",
        "key": "JWT_EXPIRATION",
        "value": "60",
        "value_type": "int",
        "description": "JWT Access token expiration lifetime in minutes",
    },
    {
        "category": "SECURITY",
        "key": "MAX_LOGIN_ATTEMPTS",
        "value": "5",
        "value_type": "int",
        "description": "Maximum failed login attempts before temporary lockout",
    },
    {
        "category": "SECURITY",
        "key": "SESSION_TIMEOUT",
        "value": "60",
        "value_type": "int",
        "description": "Inactivity session timeout in minutes",
    },
    {
        "category": "SECURITY",
        "key": "RATE_LIMIT",
        "value": "60",
        "value_type": "int",
        "description": "Maximum API requests per minute per IP",
    },
    # General Configuration
    {
        "category": "GENERAL",
        "key": "SYSTEM_ENVIRONMENT",
        "value": "production",
        "value_type": "str",
        "description": "Current system operating environment",
    },
    {
        "category": "GENERAL",
        "key": "MAINTENANCE_MODE",
        "value": "false",
        "value_type": "bool",
        "description": "Whether the system is in administrative maintenance mode",
    },
]


class ConfigService:
    def ensure_default_configs(self, db: Session) -> None:
        """Seed any missing configuration entries."""
        try:
            existing_keys = {row[0] for row in db.query(SystemConfigDB.key).all()}
            for item in DEFAULT_CONFIGS:
                if item["key"] not in existing_keys:
                    db.add(
                        SystemConfigDB(
                            category=item["category"],
                            key=item["key"],
                            value=item["value"],
                            value_type=item["value_type"],
                            description=item["description"],
                            updated_at=datetime.utcnow(),
                        )
                    )
            db.commit()
        except Exception:
            db.rollback()

    def get_all_configs(self, db: Session, category: str | None = None) -> list[dict[str, Any]]:
        self.ensure_default_configs(db)
        query = db.query(SystemConfigDB)
        if category:
            query = query.filter(SystemConfigDB.category == category.upper())
        items = query.order_by(SystemConfigDB.category, SystemConfigDB.key).all()
        return [
            {
                "id": c.id,
                "category": c.category,
                "key": c.key,
                "value": self._cast_value(c.value, c.value_type),
                "value_type": c.value_type,
                "description": c.description,
                "is_secret": c.is_secret,
                "requires_restart": c.requires_restart,
                "updated_at": c.updated_at.isoformat(),
            }
            for c in items
        ]

    def get_config_value(self, db: Session, key: str, default: Any = None) -> Any:
        self.ensure_default_configs(db)
        config = db.query(SystemConfigDB).filter(SystemConfigDB.key == key).first()
        if not config:
            return default
        return self._cast_value(config.value, config.value_type)

    def update_config(
        self,
        db: Session,
        key: str,
        new_val: Any = None,
        reason: str = "",
        user_id: int | None = None,
        *,
        value: Any = None,
        changed_by_user_id: int | None = None,
    ) -> dict[str, Any]:
        if new_val is None and value is not None:
            new_val = value
        if user_id is None and changed_by_user_id is not None:
            user_id = changed_by_user_id

        self.ensure_default_configs(db)
        config = db.query(SystemConfigDB).filter(SystemConfigDB.key == key).first()
        if not config:
            raise ValueError(f"Configuration key '{key}' not found.")

        # Validate new value
        valid_val_str = self._validate_and_serialize(key, new_val, config.value_type)
        old_val_str = config.value

        if old_val_str == valid_val_str:
            return {
                "id": config.id,
                "category": config.category,
                "key": config.key,
                "value": self._cast_value(config.value, config.value_type),
                "value_type": config.value_type,
                "updated_at": config.updated_at.isoformat(),
            }

        config.value = valid_val_str
        config.updated_at = datetime.utcnow()
        config.updated_by_user_id = user_id

        # Record immutable audit entry
        audit_entry = SystemConfigAuditDB(
            category=config.category,
            key=config.key,
            old_value=old_val_str,
            new_value=valid_val_str,
            changed_by_user_id=user_id,
            changed_at=datetime.utcnow(),
            reason=reason,
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(config)

        return {
            "id": config.id,
            "category": config.category,
            "key": config.key,
            "value": self._cast_value(config.value, config.value_type),
            "value_type": config.value_type,
            "updated_at": config.updated_at.isoformat(),
        }

    initialize_defaults = ensure_default_configs

    def get_audit_trail(
        self,
        db: Session,
        arg1: int | str | None = None,
        arg2: str | int | None = None,
        *,
        key: str | None = None,
        limit: int = 100,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        if isinstance(arg1, int):
            limit = arg1
            if isinstance(arg2, str):
                category = arg2
        elif isinstance(arg1, str):
            key = arg1
            if isinstance(arg2, int):
                limit = arg2

        query = db.query(SystemConfigAuditDB)
        if key:
            query = query.filter(SystemConfigAuditDB.key == key)
        if category:
            query = query.filter(SystemConfigAuditDB.category == category.upper())
        audits = query.order_by(SystemConfigAuditDB.changed_at.desc()).limit(limit).all()
        return [
            {
                "id": a.id,
                "category": a.category,
                "key": a.key,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "changed_by_user_id": a.changed_by_user_id,
                "changed_at": a.changed_at.isoformat(),
                "reason": a.reason,
            }
            for a in audits
        ]

    get_audit_history = get_audit_trail


    def _cast_value(self, val_str: str, val_type: str) -> Any:
        try:
            if val_type == "float":
                return float(val_str)
            if val_type == "int":
                return int(val_str)
            if val_type == "bool":
                return val_str.lower() in ("true", "1", "yes")
            if val_type == "json":
                return json.loads(val_str)
            return val_str
        except Exception:
            return val_str

    def _validate_and_serialize(self, key: str, value: Any, val_type: str) -> str:
        # Range validations
        if val_type == "float":
            try:
                fval = float(value)
            except (ValueError, TypeError):
                raise ValueError(f"Value for {key} must be a valid floating-point number.")
            if "THRESHOLD" in key or "SCORE" in key:
                if not (0.0 <= fval <= 1.0):
                    raise ValueError(f"{key} must be between 0.0 and 1.0.")
            if "INTERVAL" in key or "TIMEOUT" in key:
                if fval <= 0:
                    raise ValueError(f"{key} must be greater than 0.")
            return str(fval)

        if val_type == "int":
            try:
                ival = int(value)
            except (ValueError, TypeError):
                raise ValueError(f"Value for {key} must be a valid integer.")
            if ival < 0:
                raise ValueError(f"{key} cannot be negative.")
            if key in ("MIN_FACE_SIZE", "MATCH_TOP_K", "MAX_QUEUE_SIZE", "JWT_EXPIRATION") and ival < 1:
                raise ValueError(f"{key} must be at least 1.")
            return str(ival)

        if val_type == "bool":
            if isinstance(value, bool):
                return "true" if value else "false"
            if str(value).lower() in ("true", "1", "yes"):
                return "true"
            if str(value).lower() in ("false", "0", "no"):
                return "false"
            raise ValueError(f"Value for {key} must be a boolean.")

        if val_type == "json":
            if isinstance(value, str):
                json.loads(value)
                return value
            return json.dumps(value)

        return str(value)


config_service = ConfigService()
