import hashlib

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.analysis import ProviderResult
from app.services.ai_provider import HTTPPhotoProvider, ProviderError


@pytest.fixture
def result():
    return {
        "schema_version": "1.0",
        "model_name": "test-model",
        "model_version": "test-1",
        "is_mock": False,
        "image_usable": True,
        "limitations": ["Single-photo visual assessment only"],
        "suggestions": [
            {
                "field": "clarity",
                "value": "cloudy",
                "confidence": 0.7,
                "explanation": "Suspended particles obscure the stream bed",
            }
        ],
    }


@pytest.fixture
def provider_factory(tmp_path):
    image = tmp_path / "photo.png"
    image.write_bytes(b"contract-test-photo")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()

    def factory(handler, **changes):
        settings = Settings(
            _env_file=None,
            environment="test",
            database_url="sqlite:///ignored.db",
            ai_mode="http",
            ai_service_url="https://ai.example.com/analyze",
            ai_service_token="test-only-token",
            **changes,
        )
        return HTTPPhotoProvider(settings, httpx.MockTransport(handler)), image, digest

    return factory


def test_real_http_adapter_contract_and_data_minimization(provider_factory, result):
    seen = []

    def handler(request):
        seen.append(request)
        body = request.read()
        assert request.url == "https://ai.example.com/analyze"
        assert request.headers["authorization"] == "Bearer test-only-token"
        assert request.headers["idempotency-key"] == "request-123"
        assert b'filename="observation.png"' in body
        assert b'name="photo_sha256"' in body
        assert b"email" not in body and b"contributor" not in body and b"notes" not in body
        return httpx.Response(200, json=result)

    provider, photo, digest = provider_factory(handler)
    assert provider.analyze(photo, digest, "request-123").model_name == "test-model"
    assert len(seen) == 1


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(503, text="private provider failure"), "provider_http_error"),
        (httpx.Response(302, headers={"Location": "https://other.example"}), "provider_http_error"),
        (httpx.Response(200, text="not json"), "invalid_response"),
        (
            httpx.Response(200, content=b'{"bad": true}', headers={"Content-Type": "application/json"}),
            "invalid_response",
        ),
        (
            httpx.Response(200, content=b"x" * 2048, headers={"Content-Type": "application/json"}),
            "response_too_large",
        ),
        (
            httpx.Response(
                200, content=b'{"duplicate":1,"duplicate":2}', headers={"Content-Type": "application/json"}
            ),
            "invalid_response",
        ),
    ],
)
def test_http_failures_are_sanitized(provider_factory, response, code):
    provider, photo, digest = provider_factory(lambda request: response, ai_max_response_bytes=1024)
    with pytest.raises(ProviderError) as error:
        provider.analyze(photo, digest, "r")
    assert error.value.code == code
    assert "private provider" not in str(error.value) and "test-only-token" not in str(error.value)


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ReadTimeout("secret-url"), "provider_timeout"),
        (httpx.ConnectError("secret-url"), "provider_unavailable"),
    ],
)
def test_network_failures(provider_factory, exception, code):
    def fail(request):
        raise exception

    provider, photo, digest = provider_factory(fail)
    with pytest.raises(ProviderError) as error:
        provider.analyze(photo, digest, "r")
    assert error.value.code == code and "secret-url" not in str(error.value)


def test_photo_digest_and_missing_file(provider_factory, result):
    provider, photo, digest = provider_factory(lambda request: httpx.Response(200, json=result))
    with pytest.raises(ProviderError) as error:
        provider.analyze(photo, "0" * 64, "r")
    assert error.value.code == "photo_changed"
    photo.unlink()
    with pytest.raises(ProviderError) as error:
        provider.analyze(photo, digest, "r")
    assert error.value.code == "photo_unavailable"


@pytest.mark.parametrize(
    "change",
    [
        {"field": "smell", "value": "chemical"},
        {"field": "ph", "value": "7"},
        {"field": "flow", "value": "fast"},
        {"confidence": 1.01},
        {"confidence": "0.7"},
        {"value": "invented"},
        {"explanation": " "},
        {"evidence_region": {"x": 0.9, "y": 0.0, "width": 0.2, "height": 0.1}},
    ],
)
def test_invalid_suggestions_rejected(result, change):
    result["suggestions"][0].update(change)
    with pytest.raises(ValidationError):
        ProviderResult.model_validate(result)


def test_unknown_keys_duplicates_and_unusable_images(result):
    with pytest.raises(ValidationError):
        ProviderResult.model_validate({**result, "trust_score": 99})
    with pytest.raises(ValidationError):
        ProviderResult.model_validate({**result, "suggestions": result["suggestions"] * 2})
    with pytest.raises(ValidationError):
        ProviderResult.model_validate({**result, "image_usable": False})
    assert (
        ProviderResult.model_validate({**result, "image_usable": False, "suggestions": []}).suggestions == []
    )


def test_live_service_cannot_return_mock(provider_factory, result):
    provider, photo, digest = provider_factory(
        lambda request: httpx.Response(200, json={**result, "is_mock": True})
    )
    with pytest.raises(ProviderError) as error:
        provider.analyze(photo, digest, "r")
    assert error.value.code == "invalid_response"


def test_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_mode="http", ai_service_url=None)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_service_url="https://user:pass@ai.example/analyze")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql://user:pass@localhost/db",
            ai_mode="mock",
        )
