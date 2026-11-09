from __future__ import annotations

import base64
from enum import Enum
import hashlib
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.camera import Camera, CameraStatus
from app.models.department import Department
from app.models.user import User
from app.schemas.camera import CameraCreateRequest, CameraUpdateRequest


class CameraService:
    @staticmethod
    def _fernet() -> Fernet:
        key = settings.STREAM_ENCRYPTION_KEY.strip() or settings.SECRET_KEY
        try:
            return Fernet(key.encode())
        except (ValueError, TypeError):
            # Derive 32-byte URL-safe base64 key from sha256
            return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))

    @classmethod
    def encrypt_password(cls, password: str | None) -> str | None:
        if password is None:
            return None
        return cls._fernet().encrypt(password.encode()).decode()

    @classmethod
    def decrypt_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return cls._fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Stored stream password cannot be decrypted") from exc

    @staticmethod
    def validate_url(url: str) -> str:
        value = url.strip()
        # Allow local webcam device indices (e.g. "0", "1")
        if value.isdigit():
            return value
        # Allow file:// and local video file paths
        if value.startswith("file://") or value.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".m4v")):
            return value
        if value.startswith("test:") or value.startswith("prerecorded:"):
            return value

        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"rtsp", "http", "https"} or not parsed.netloc:
            raise ValueError("Stream URL must use RTSP, HTTP, or HTTPS, a webcam device index, or a video file path")
        if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
            raise ValueError("Stream URL must not contain embedded credentials")
        return value

    @staticmethod
    def validate_stream_type(stream_type: str | Enum | None, url: str) -> str:
        clean = url.strip()
        if clean.isdigit():
            return "WEBCAM"
        if clean.startswith("file://") or clean.lower().endswith((".mp4", ".avi", ".mkv", ".mov")):
            return "FILE"
        if clean.startswith("test:") or clean.startswith("prerecorded:"):
            return "PRERECORDED"

        parsed_scheme = urlsplit(clean).scheme.upper()
        if stream_type is None:
            return parsed_scheme or "RTSP"

        value = stream_type.value if isinstance(stream_type, Enum) else str(stream_type).upper()
        allowed = {"RTSP", "HTTP", "HTTPS", "FILE", "WEBCAM", "TEST", "PRERECORDED"}
        if value not in allowed:
            raise ValueError(f"Stream type must be one of {allowed}")
        return value

    @staticmethod
    def can_access(user: User, camera: Camera) -> bool:
        if user.role == "ADMIN":
            return True
        return user.department_id is not None and user.department_id == camera.department_id

    @staticmethod
    def ensure_department(db: Session, department_id: int) -> Department:
        dept = db.query(Department).filter(Department.id == department_id).first()
        if dept is None:
            raise ValueError("Department not found")
        return dept

    @classmethod
    def create(cls, db: Session, user: User, payload: CameraCreateRequest) -> Camera:
        cls.ensure_department(db, payload.department_id)
        url = cls.validate_url(payload.stream_url)
        stype = cls.validate_stream_type(payload.stream_type, url)
        name = payload.camera_name or payload.name or "CCTV Camera"

        encrypted_pwd = cls.encrypt_password(payload.password) if payload.password else None
        init_status = CameraStatus.ACTIVE.value if payload.is_active else CameraStatus.INACTIVE.value

        camera = Camera(
            camera_code=payload.camera_code or None,
            camera_name=name,
            department_id=payload.department_id,
            location_name=payload.location_name,
            latitude=payload.latitude,
            longitude=payload.longitude,
            jurisdiction=payload.jurisdiction,
            description=payload.description,
            stream_url=url,
            stream_type=stype,
            username_reference=payload.username_reference,
            encrypted_password=encrypted_pwd,
            status=init_status,
            is_active=payload.is_active,
            sample_fps=payload.sample_fps,
            queue_size=payload.queue_size,
            retry_limit=payload.retry_limit,
        )

        db.add(camera)
        db.commit()
        db.refresh(camera)

        cls.log(
            db,
            user.id,
            "CAMERA_REGISTERED",
            camera.id,
            f"Registered camera '{camera.camera_name}' (code: {camera.camera_code})",
        )
        return camera

    @classmethod
    def update(cls, db: Session, user: User, camera: Camera, payload: CameraUpdateRequest) -> Camera:
        values = payload.model_dump(exclude_unset=True)

        if "department_id" in values and values["department_id"] is not None:
            cls.ensure_department(db, values["department_id"])

        if "stream_url" in values and values["stream_url"] is not None:
            values["stream_url"] = cls.validate_url(values["stream_url"])

        if "password" in values:
            raw_pwd = values.pop("password")
            camera.encrypted_password = cls.encrypt_password(raw_pwd) if raw_pwd else None

        name = values.get("camera_name") or values.get("name")
        if name:
            camera.camera_name = name
            values.pop("name", None)
            values.pop("camera_name", None)

        url = values.get("stream_url", camera.stream_url)
        if "stream_type" in values or "stream_url" in values:
            values["stream_type"] = cls.validate_stream_type(
                values.get("stream_type", camera.stream_type), url
            )

        if "is_active" in values and values["is_active"] is not None:
            values["status"] = (
                CameraStatus.ACTIVE.value if values["is_active"] else CameraStatus.INACTIVE.value
            )

        for key, value in values.items():
            if hasattr(camera, key):
                setattr(camera, key, value)

        db.commit()
        db.refresh(camera)

        cls.log(
            db,
            user.id,
            "CAMERA_UPDATED",
            camera.id,
            f"Updated camera fields: {', '.join(values.keys())}",
        )
        return camera

    @classmethod
    def set_status(
        cls,
        db: Session,
        user: User,
        camera: Camera,
        new_status: CameraStatus | str,
    ) -> Camera:
        status_val = new_status.value if isinstance(new_status, Enum) else str(new_status).upper()
        if status_val not in {
            CameraStatus.ACTIVE.value,
            CameraStatus.INACTIVE.value,
            CameraStatus.ONLINE.value,
            CameraStatus.OFFLINE.value,
            CameraStatus.ERROR.value,
            CameraStatus.CONNECTING.value,
        }:
            raise ValueError(f"Invalid camera status: {new_status}")

        camera.status = status_val
        if status_val == CameraStatus.INACTIVE.value:
            camera.is_active = False
        elif status_val == CameraStatus.ACTIVE.value:
            camera.is_active = True

        db.commit()
        db.refresh(camera)

        action = "CAMERA_ACTIVATED" if camera.is_active else "CAMERA_DEACTIVATED"
        cls.log(
            db,
            user.id,
            action,
            camera.id,
            f"Camera status set to {status_val}",
        )
        return camera

    @staticmethod
    def log(
        db: Session,
        user_id: int | None,
        action: str,
        camera_id: int | None,
        details: str | None = None,
    ) -> None:
        try:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type="CAMERA",
                    resource_id=camera_id,
                    details=details,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
