import asyncio
import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def _get_keys() -> list[str]:
    if settings.GEMINI_API_KEYS:
        return [k.strip() for k in settings.GEMINI_API_KEYS.split(",") if k.strip()]
    if settings.GEMINI_API_KEY:
        return [settings.GEMINI_API_KEY]
    return []


async def analyze_image(
    image_bytes: bytes,
    mime_type: str,
    prompt: str = "Bu rasmni batafsil tavsiflab bering. O'zbek tilida javob bering.",
) -> str:
    keys = _get_keys()
    if not keys:
        return "Gemini API kaliti sozlanmagan."

    image_b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                ]
            }
        ]
    }

    last_error = ""
    for key in keys:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GEMINI_URL, params={"key": key}, json=payload, timeout=60
            )

        if resp.status_code == 429:
            logger.warning("Gemini image rate limit, rotating key")
            await asyncio.sleep(0.5)
            continue

        if resp.status_code != 200:
            last_error = f"{resp.status_code} — {resp.text[:200]}"
            continue

        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            last_error = "Gemini javob bera olmadi"
            continue

    return f"Gemini xatolik: {last_error}"
