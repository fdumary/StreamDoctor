import hashlib
import io
import json
from uuid import uuid4

import httpx
import pytest
from app.core.config import Settings as BackendSettings
from app.services.ai_provider import HTTPPhotoProvider
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from ai_agent.inference import GeminiVision
from ai_agent.main import create_app
from ai_agent.settings import Settings

TOKEN = "test-service-token-for-integration"


def png(color="blue"):
    out = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(out, "PNG")
    return out.getvalue()


def settings(**kwargs):
    return Settings(
        _env_file=None, service_token=TOKEN, api_key="test-only-key", **kwargs
    )


def response_payload():
    return {
        "image_usable": True,
        "limitations": ["Test fixture, not measured inference"],
        "suggestions": [
            {
                "field": "clarity",
                "value": "cloudy",
                "explanation": "Test fixture showing cloudiness",
            }
        ],
    }


def model_transport(payload=None, status=200):
    def handler(request):
        data = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "test-only-key"
        assert data["generationConfig"]["responseMimeType"] == "application/json"
        assert data["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/jpeg"
        return httpx.Response(
            status,
            json={
                "modelVersion": "test-model",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        payload
                                        if payload is not None
                                        else response_payload()
                                    )
                                }
                            ]
                        },
                    }
                ],
            },
        )

    return httpx.MockTransport(handler)


def test_backend_to_service_to_model_contract(tmp_path):
    config = settings()
    service = create_app(config, GeminiVision(config, transport=model_transport()))
    with TestClient(service) as client:

        def bridge(request):
            reply = client.post(
                "/analyze", content=request.read(), headers=dict(request.headers)
            )
            return httpx.Response(
                reply.status_code, content=reply.content, headers=reply.headers
            )

        backend = BackendSettings(
            _env_file=None,
            ai_mode="http",
            ai_service_url="http://vision/analyze",
            ai_service_token=TOKEN,
        )
        path = tmp_path / "photo.png"
        path.write_bytes(png())
        result = HTTPPhotoProvider(
            backend, transport=httpx.MockTransport(bridge)
        ).analyze(path, hashlib.sha256(path.read_bytes()).hexdigest(), str(uuid4()))
        assert result.is_mock is False
        assert result.suggestions[0].confidence is None
        assert result.suggestions[0].value == "cloudy"


def test_auth_digest_and_retry_cache():
    config = settings()
    calls = []

    class Provider:
        def analyze(self, raw):
            calls.append(raw)
            return {"fixture": True}

    with TestClient(create_app(config, Provider())) as client:
        raw = png()
        data = {
            "schema_version": "1.0",
            "request_id": str(uuid4()),
            "photo_sha256": hashlib.sha256(raw).hexdigest(),
        }
        files = {"file": ("photo.png", raw, "image/png")}
        assert client.post("/analyze", data=data, files=files).status_code == 401
        headers = {"Authorization": f"Bearer {TOKEN}"}
        for _ in range(2):
            assert (
                client.post(
                    "/analyze", data=data, files=files, headers=headers
                ).status_code
                == 200
            )
        assert len(calls) == 1
        assert (
            client.post(
                "/analyze",
                data={**data, "photo_sha256": "0" * 64},
                files=files,
                headers=headers,
            ).status_code
            == 422
        )
        different = png("green")
        assert (
            client.post(
                "/analyze",
                data={**data, "photo_sha256": hashlib.sha256(different).hexdigest()},
                files={"file": ("photo.png", different)},
                headers=headers,
            ).status_code
            == 409
        )


@pytest.mark.parametrize(
    "payload",
    [
        {**response_payload(), "image_usable": False},
        {
            **response_payload(),
            "suggestions": [
                {
                    "field": "smell",
                    "value": "chemical",
                    "explanation": "Invalid visual claim",
                }
            ],
        },
        {**response_payload(), "suggestions": response_payload()["suggestions"] * 2},
    ],
)
def test_invalid_model_output_fails_without_fallback(payload):
    with pytest.raises(HTTPException) as error:
        GeminiVision(settings(), model_transport(payload)).analyze(png())
    assert error.value.status_code == 502


def test_quota_timeout_and_invalid_photo():
    with pytest.raises(HTTPException) as error:
        GeminiVision(settings(), model_transport(status=429)).analyze(png())
    assert error.value.status_code == 429

    def timeout(request):
        raise httpx.ReadTimeout("fixture timeout")

    with pytest.raises(HTTPException) as error:
        GeminiVision(settings(), httpx.MockTransport(timeout)).analyze(png())
    assert error.value.status_code == 504
    with pytest.raises(HTTPException) as error:
        GeminiVision(settings(), model_transport()).analyze(b"not an image")
    assert error.value.status_code == 422


def test_missing_configuration_fails_closed():
    with TestClient(
        create_app(Settings(_env_file=None, api_key=None, service_token=None))
    ) as client:
        assert client.get("/health/ready").status_code == 503
        assert client.post("/analyze", content=b"bad body").status_code == 503
