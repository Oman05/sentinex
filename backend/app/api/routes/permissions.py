from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin, require_police
from app.models.user import User

router = APIRouter(tags=["permissions"])


@router.get("/admin/test")
def admin_test(current_user: User = Depends(require_admin)):
    return {"message": "Admin access granted", "user": current_user.username, "role": current_user.role}


@router.get("/police/test")
def police_test(current_user: User = Depends(require_police)):
    return {"message": "Police access granted", "user": current_user.username, "role": current_user.role}
