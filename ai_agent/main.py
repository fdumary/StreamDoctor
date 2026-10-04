import hashlib
import hmac
import threading
from collections import OrderedDict
from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette.responses import JSONResponse

from ai_agent.inference import GeminiVision
from ai_agent.settings import Settings


class InferenceGate:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") != "/analyze":
            return await self.app(scope, receive, send)
        token = self.settings.service_token
        if not token or len(token.get_secret_value()) < 16:
            return await JSONResponse(
                {"detail": "AI service token is not configured"}, status_code=503
            )(scope, receive, send)
        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"authorization", b"")
        expected = ("Bearer " + token.get_secret_value()).encode()
        if not hmac.compare_digest(supplied, expected):
            return await JSONResponse(
                {"detail": "Invalid service credentials"}, status_code=401
            )(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.settings.max_photo_bytes + 512 * 1024:
                return await JSONResponse(
                    {"detail": "Image request is too large"}, status_code=413
                )(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)


def create_app(settings=None, provider=None):
    settings = settings or Settings()
    app = FastAPI(title="StreamDoctor Vision", version="1.0.0")
    app.add_middleware(InferenceGate, settings=settings)
    app.state.provider = provider or GeminiVision(settings)
    cache, active = OrderedDict(), set()
    lock = threading.Lock()
    capacity = threading.BoundedSemaphore(settings.max_concurrency)

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        if (
            not settings.api_key
            or not settings.api_key.get_secret_value().strip()
            or not settings.service_token
            or len(settings.service_token.get_secret_value()) < 16
        ):
            raise HTTPException(503, "Configure GEMINI_API_KEY and AI_SERVICE_TOKEN")
        return {"status": "ready", "model": settings.model}

    @app.post("/analyze")
    def analyze(
        file: Annotated[UploadFile, File()],
        schema_version: Annotated[Literal["1.0"], Form()],
        request_id: Annotated[UUID, Form()],
        photo_sha256: Annotated[str, Form(pattern=r"^[a-f0-9]{64}$")],
    ):
        raw = file.file.read(settings.max_photo_bytes + 1)
        if not raw or len(raw) > settings.max_photo_bytes:
            raise HTTPException(413, "Photo is empty or too large")
        if hashlib.sha256(raw).hexdigest() != photo_sha256:
            raise HTTPException(422, "Photo digest does not match")
        key = str(request_id)
        with lock:
            now = monotonic()
            for expired in [
                k
                for k, item in cache.items()
                if now - item[0] >= settings.cache_ttl_seconds
            ]:
                cache.pop(expired)
            if key in cache:
                _, digest, result = cache[key]
                if digest != photo_sha256:
                    raise HTTPException(
                        409, "Request ID already used with a different photo"
                    )
                cache.move_to_end(key)
                return result
            if key in active or not capacity.acquire(blocking=False):
                raise HTTPException(429, "AI service is busy; retry shortly")
            active.add(key)
        try:
            result = app.state.provider.analyze(raw)
            with lock:
                cache[key] = (monotonic(), photo_sha256, result)
                while len(cache) > settings.cache_size:
                    cache.popitem(last=False)
            return result
        finally:
            with lock:
                active.discard(key)
            capacity.release()

    return app


app = create_app()
