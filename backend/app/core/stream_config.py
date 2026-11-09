from app.core.config import settings


class StreamConfig:
    enabled: bool = settings.STREAMING_ENABLED
    default_sample_fps: float = settings.STREAM_DEFAULT_SAMPLE_FPS
    default_queue_size: int = settings.STREAM_DEFAULT_QUEUE_SIZE
    retry_limit: int = settings.STREAM_RETRY_LIMIT
    retry_backoff_seconds: float = settings.STREAM_RETRY_BACKOFF_SECONDS
    health_interval_seconds: float = settings.STREAM_HEALTH_INTERVAL_SECONDS
    encryption_key: str = settings.STREAM_ENCRYPTION_KEY


stream_config = StreamConfig()
