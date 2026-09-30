from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import require_reviewer
from app.models.user import User

router = APIRouter(prefix="/reviewer", tags=["Reviewer permissions"])


@router.get("/access")
def reviewer_access(user: Annotated[User, Depends(require_reviewer)]):
    """Phase 1 permission check. The review queue arrives in Phase 4."""
    return {"allowed": True, "role": user.role}
