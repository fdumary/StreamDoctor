from time import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import token_digest
from app.models.auth_session import AuthSession
from app.models.user import Role, User

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    with request.app.state.session_factory() as session:
        yield session


Database = Annotated[Session, Depends(get_db)]


def current_session(
    db: Database,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthSession:
    failure = HTTPException(401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"})
    if not credentials or len(credentials.credentials) > 256:
        raise failure
    session = db.get(AuthSession, token_digest(credentials.credentials))
    if not session or session.expires_at <= int(time()):
        raise failure
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise failure
    return session


def current_user(db: Database, session: Annotated[AuthSession, Depends(current_session)]) -> User:
    return db.get(User, session.user_id)


CurrentUser = Annotated[User, Depends(current_user)]


def require_reviewer(user: CurrentUser) -> User:

    if user.role != Role.reviewer:
        raise HTTPException(403, "Reviewer role required")
    return user
