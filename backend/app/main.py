from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, health, reviewer, users
from app.core.config import Settings, get_settings
from app.core.rate_limit import AuthRateLimiter
from app.db.session import make_engine, make_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    api = FastAPI(
        title="StreamDoctor API",
        version="0.1.0",
        description="Phase 1: accounts, sessions, roles, and database foundation.",
    )
    api.state.settings = settings
    api.state.engine = make_engine(settings.database_url)
    api.state.session_factory = make_session_factory(api.state.engine)
    api.state.auth_limiter = AuthRateLimiter(settings.auth_rate_limit, settings.auth_rate_window_seconds)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @api.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Never echo invalid password values back in validation errors.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @api.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    for router in (auth.router, users.router, reviewer.router):
        api.include_router(router, prefix="/api/v1")
    api.include_router(health.router)
    return api


app = create_app()
