from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, health, photos, reports, reviewer, sites, users
from app.core.body_limit import RequestBodyLimit
from app.core.config import Settings, get_settings
from app.core.rate_limit import AuthRateLimiter
from app.db.session import make_engine, make_session_factory
from app.services.storage import LocalPhotoStorage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    api = FastAPI(
        title="StreamDoctor API",
        version="0.2.0",
        description="Phase 2: accounts, stream sites, volunteer reports, and private photo uploads.",
    )
    api.state.settings = settings
    api.state.photo_storage = LocalPhotoStorage(settings.upload_dir)
    api.add_middleware(RequestBodyLimit, photo_limit=settings.max_photo_bytes + 512 * 1024)
    api.state.engine = make_engine(settings.database_url)
    api.state.session_factory = make_session_factory(api.state.engine)
    api.state.auth_limiter = AuthRateLimiter(settings.auth_rate_limit, settings.auth_rate_window_seconds)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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

    for router in (auth.router, users.router, reviewer.router, sites.router, reports.router, photos.router):
        api.include_router(router, prefix="/api/v1")
    api.include_router(health.router)
    return api


app = create_app()
