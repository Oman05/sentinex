"""Dependencies for FastAPI route handlers."""

from app.dependencies.auth import get_current_user, require_admin, require_police

__all__ = ["get_current_user", "require_admin", "require_police"]
