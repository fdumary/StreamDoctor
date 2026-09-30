from time import time

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_PASSWORD_HASH, hash_password, new_token, token_digest, verify_password
from app.models.auth_session import AuthSession
from app.models.user import Role, User
from app.schemas.auth import Credentials, RegisterRequest


def register(db: Session, data: RegisterRequest) -> User:
    user = User(
        email=str(data.email),
        display_name=data.display_name,
        password_hash=hash_password(data.password),
        role=Role.volunteer,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    db.refresh(user)
    return user


def login(db: Session, data: Credentials, ttl_minutes: int) -> str:
    user = db.scalar(select(User).where(User.email == str(data.email)))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not valid or not user.is_active:
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    now = int(time())
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = new_token()
    db.add(AuthSession(token_hash=token_digest(token), user_id=user.id, expires_at=now + ttl_minutes * 60))
    db.commit()
    return token
