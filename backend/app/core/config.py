from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite:///./sentinex.db"
    DATASET_ROOT: str = "./datasets"
    MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024
    MAX_IMAGE_DIMENSION: int = 10000
    STREAMING_ENABLED: bool = True
    STREAM_ENCRYPTION_KEY: str = ""
    STREAM_DEFAULT_SAMPLE_FPS: float = 1.0
    STREAM_DEFAULT_QUEUE_SIZE: int = 8
    STREAM_RETRY_LIMIT: int = 3
    STREAM_RETRY_BACKOFF_SECONDS: float = 2.0
    STREAM_HEALTH_INTERVAL_SECONDS: float = 5.0

    # Module 9: Alert & Department Notification System
    ALERT_ACK_TIMEOUT_MINUTES: int = 15
    ALERT_MAX_RETRY_COUNT: int = 3
    ALERT_ESCALATION_ENABLED: bool = True
    ALERT_DEDUP_WINDOW_MINUTES: int = 60
    ALERT_EMAIL_MODE: str = "DEV"  # DEV (simulated sandbox/log), SMTP, or MOCK
    ALERT_DEV_EMAIL_SINK: str = "dev-inbox@sentinex.local"
    ALERT_DISPATCH_SMS_ENABLED: bool = False
    ALERT_DISPATCH_PUSH_ENABLED: bool = False

    # Module 10: Evidence Management & Audit Trail
    EVIDENCE_ROOT: str = "./evidence_store"
    EVIDENCE_STORAGE_BACKEND: str = "LOCAL"        # LOCAL | S3 | AZURE_BLOB | GCS
    EVIDENCE_MAX_IMAGE_BYTES: int = 20 * 1024 * 1024   # 20 MB
    EVIDENCE_MAX_VIDEO_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GB
    EVIDENCE_MAX_DOC_BYTES: int = 50 * 1024 * 1024   # 50 MB
    EVIDENCE_MALWARE_SCAN_ENABLED: bool = False    # Set True and wire ClamAV for production
    EVIDENCE_CLIP_WINDOW_SECONDS: int = 10         # ±seconds around event for auto clip

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()


