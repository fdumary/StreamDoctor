import hashlib
import json
from time import monotonic

import httpx
from pydantic import ValidationError

from app.schemas.analysis import ProviderResult


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class MockPhotoProvider:
    """Fixed UI fixture. Does not inspect pixels or perform inference."""

    def analyze(self, photo_path, photo_hash: str, request_id: str) -> ProviderResult:
        return ProviderResult.model_validate(
            {
                "schema_version": "1.0",
                "model_name": "streamdoctor-demo-fixture",
                "model_version": "1",
                "is_mock": True,
                "image_usable": True,
                "limitations": [
                    "SIMULATED result: fixed suggestions for integration testing; no image analysis was performed."
                ],
                "suggestions": [
                    {
                        "field": "clarity",
                        "value": "cloudy",
                        "confidence": None,
                        "explanation": "SIMULATED suggestion to demonstrate accepting or editing an observation.",
                    },
                    {
                        "field": "foam",
                        "value": "small_patches",
                        "confidence": None,
                        "explanation": "SIMULATED suggestion to demonstrate rejecting an observation.",
                    },
                ],
            }
        )


class HTTPPhotoProvider:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    def analyze(self, photo_path, photo_hash: str, request_id: str) -> ProviderResult:
        settings = self.settings
        headers = {"Accept": "application/json", "Accept-Encoding": "identity", "Idempotency-Key": request_id}
        if settings.ai_service_token:
            headers["Authorization"] = "Bearer " + settings.ai_service_token.get_secret_value()
        start = monotonic()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    settings.ai_timeout_seconds, connect=min(5, settings.ai_timeout_seconds)
                ),
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
            ) as client:
                with photo_path.open("rb") as photo:
                    if hashlib.file_digest(photo, "sha256").hexdigest() != photo_hash:
                        raise ProviderError(
                            "photo_changed", "Stored photo does not match its recorded digest"
                        )
                    photo.seek(0)
                    with client.stream(
                        "POST",
                        settings.ai_service_url,
                        headers=headers,
                        files={"file": ("observation.png", photo, "image/png")},
                        data={"schema_version": "1.0", "request_id": request_id, "photo_sha256": photo_hash},
                    ) as response:
                        if response.status_code != 200:
                            raise ProviderError(
                                "provider_http_error", "AI service did not return a successful response"
                            )
                        if (
                            response.headers.get("content-type", "").split(";", 1)[0].strip()
                            != "application/json"
                        ):
                            raise ProviderError("invalid_response", "AI service must return JSON")
                        if response.headers.get("content-encoding", "identity") != "identity":
                            raise ProviderError(
                                "invalid_response", "Compressed AI responses are not supported"
                            )
                        content = bytearray()
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if monotonic() - start > settings.ai_timeout_seconds:
                                raise ProviderError(
                                    "provider_timeout", "AI service response exceeded the time limit"
                                )
                            content.extend(chunk)
                            if len(content) > settings.ai_max_response_bytes:
                                raise ProviderError(
                                    "response_too_large", "AI service response exceeded the size limit"
                                )

            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON key")
                    result[key] = value
                return result

            def invalid_constant(value):
                raise ValueError("Non-finite JSON number")

            payload = json.loads(content, object_pairs_hook=unique_object, parse_constant=invalid_constant)
            result = ProviderResult.model_validate(payload)
            if result.is_mock:
                raise ProviderError("invalid_response", "Live AI service returned a simulated result")
            return result
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "provider_timeout", "AI service timed out; the report is still saved"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "provider_unavailable", "AI service is unavailable; the report is still saved"
            ) from exc
        except (ValidationError, ValueError, UnicodeError) as exc:
            raise ProviderError("invalid_response", "AI service returned an invalid analysis") from exc
        except OSError as exc:
            raise ProviderError("photo_unavailable", "Photo storage is unavailable") from exc


def make_provider(settings):
    return MockPhotoProvider() if settings.ai_mode == "mock" else HTTPPhotoProvider(settings)
