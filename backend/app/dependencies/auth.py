"""Authentication dependency injectors for FastAPI route handlers."""

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(None, description="Access token via query param (e.g. for img streaming)"),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user from JWT token (Bearer header or query param).
    
    Args:
        credentials: HTTP Bearer token from the request
        token: Query parameter token (used by browser <img> src tags)
        db: Database session
        
    Returns:
        The authenticated User object
        
    Raises:
        HTTPException: If token is missing, invalid, or user not found
    """
    raw_token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = decode_access_token(raw_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing user identifier")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current user has ADMIN role."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_police(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current user has POLICE or ADMIN role."""
    allowed = {UserRole.ADMIN.value, UserRole.POLICE.value, UserRole.AUTHORIZED_OFFICER.value}
    if current_user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Police / Officer access required")
    return current_user


def require_officer(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current user has OFFICER, POLICE, or ADMIN role."""
    allowed = {UserRole.ADMIN.value, UserRole.POLICE.value, UserRole.AUTHORIZED_OFFICER.value}
    if current_user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Officer access required")
    return current_user


def require_reviewer(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current user has REVIEWER or ADMIN role."""
    allowed = {UserRole.ADMIN.value, UserRole.REVIEWER.value}
    if current_user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer access required")
    return current_user


def require_researcher(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the current user has RESEARCHER or ADMIN role."""
    allowed = {UserRole.ADMIN.value, UserRole.RESEARCHER.value}
    if current_user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Researcher access required")
    return current_user

