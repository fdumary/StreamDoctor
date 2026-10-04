import base64
import io
import json
import warnings

import httpx
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from ai_agent.explainability import PROMPT, provider_response
from ai_agent.schema import VisionResult


class GeminiVision:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    def analyze(self, image_bytes):
        settings = self.settings
        if not settings.api_key or not settings.api_key.get_secret_value().strip():
            raise HTTPException(503, "Gemini API key is not configured")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(image_bytes)) as source:
                    if (
                        source.format != "PNG"
                        or source.width * source.height > settings.max_pixels
                    ):
                        raise HTTPException(
                            422, "Expected a normalized PNG within the pixel limit"
                        )
                    if getattr(source, "n_frames", 1) != 1:
                        raise HTTPException(422, "Animated images are not supported")
                    source.load()
                    image = source.convert("RGB")
                    image.thumbnail((1568, 1568))
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=88)
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise HTTPException(422, "Image cannot be decoded safely") from exc
        payload = {
            "systemInstruction": {"parts": [{"text": PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "Assess the visible stream observations in this photo."
                        },
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": base64.b64encode(output.getvalue()).decode(),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": VisionResult.model_json_schema(),
                "maxOutputTokens": 4096,
            },
        }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(settings.timeout, connect=5),
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
            ) as client:
                with client.stream(
                    "POST",
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.model}:generateContent",
                    headers={
                        "x-goog-api-key": settings.api_key.get_secret_value(),
                        "Accept-Encoding": "identity",
                    },
                    json=payload,
                ) as response:
                    if response.status_code == 429:
                        raise HTTPException(
                            429,
                            "AI provider quota reached; retry later or submit for expert review",
                        )
                    if response.status_code != 200:
                        raise HTTPException(
                            502,
                            "AI provider rejected the request; check server configuration",
                        )
                    data = bytearray()
                    for chunk in response.iter_bytes(8192):
                        data.extend(chunk)
                        if len(data) > 512 * 1024:
                            raise HTTPException(
                                502, "AI response exceeded the size limit"
                            )
            body = json.loads(data)
            candidate = body["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Incomplete or blocked model response")
            text = "".join(
                part.get("text", "")
                for part in candidate["content"]["parts"]
                if not part.get("thought")
            )
            result = VisionResult.model_validate_json(text)
            return provider_response(
                result, settings.model, body.get("modelVersion", settings.model)
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "AI provider timed out") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, "AI provider could not be reached") from exc
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise HTTPException(
                502, "AI provider returned an invalid visual assessment"
            ) from exc
