from datetime import datetime

import pytest

from app.schemas.camera import validate_stream_url
from app.services.camera_service import CameraService
from app.services.stream_health_service import StreamHealthService
from app.utils.frame_queue import BoundedFrameQueue, FrameMetadata


def test_stream_url_validation_rejects_credentials_and_unknown_scheme():
    assert validate_stream_url("rtsp://camera.local/live") == "rtsp://camera.local/live"
    with pytest.raises(ValueError):
        validate_stream_url("rtsp://user:secret@camera.local/live")
    with pytest.raises(ValueError):
        validate_stream_url("ftp://camera.local/live")


def test_camera_password_is_encrypted_and_round_trips():
    encrypted = CameraService.encrypt_password("camera-secret")
    assert encrypted is not None
    assert encrypted != "camera-secret"
    assert CameraService.decrypt_password(encrypted) == "camera-secret"


def test_bounded_queue_drops_oldest_frame():
    queue = BoundedFrameQueue(maxsize=1)
    queue.put_nowait(FrameMetadata(1, datetime.utcnow(), "first", 1))
    queue.put_nowait(FrameMetadata(1, datetime.utcnow(), "second", 2))
    assert queue.dropped_frames == 1
    assert queue._queue.get_nowait().frame == "second"


def test_stream_health_transitions():
    service = StreamHealthService()
    service.record_connecting(1)
    service.record_failure(1, "timeout")
    assert service.get(1).status == "ERROR"
    service.record_frame(1)
    assert service.get(1).status == "ONLINE"
    assert service.get(1).failures == 0
