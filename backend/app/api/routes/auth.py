from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import Database, current_session
from app.core.rate_limit import limit_auth
from app.models.auth_session import AuthSession
from app.schemas.auth import Credentials, RegisterRequest, TokenResponse, UserResponse
from app.services import auth

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201, dependencies=[Depends(limit_auth)])
def register(data: RegisterRequest, db: Database):
    return auth.register(db, data)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit_auth)])
def login(data: Credentials, db: Database, request: Request, response: Response):
    ttl = request.app.state.settings.session_ttl_minutes
    token = auth.login(db, data, ttl)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=token, expires_in=ttl * 60)


@router.post("/logout", status_code=204)
def logout(db: Database, session: Annotated[AuthSession, Depends(current_session)]):
    db.delete(session)
    db.commit()
    return Response(status_code=204)
