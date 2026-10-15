import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004"


def _get_gemini_keys() -> list[str]:
    if settings.GEMINI_API_KEYS:
        return [k.strip() for k in settings.GEMINI_API_KEYS.split(",") if k.strip()]
    if settings.GEMINI_API_KEY:
        return [settings.GEMINI_API_KEY]
    return []


async def _embed_batch_with_key(
    texts: list[str], key: str, task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]] | None:
    requests = [
        {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": t}]},
            "taskType": task_type,
        }
        for t in texts
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{EMBED_URL}:batchEmbedContents",
            params={"key": key},
            json={"requests": requests},
            timeout=60,
        )

    if resp.status_code == 429:
        logger.warning("Gemini rate limit hit, rotating key")
        return None
    if resp.status_code != 200:
        logger.error("Gemini embedding error %s: %s", resp.status_code, resp.text[:200])
        return None

    data = resp.json()
    return [e["values"] for e in data["embeddings"]]


async def embed_texts(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    keys = _get_gemini_keys()
    if not keys:
        raise RuntimeError("No Gemini API keys configured")

    # Batch in groups of 100 (API limit)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        result = None

        for key in keys:
            result = await _embed_batch_with_key(batch, key, task_type)
            if result is not None:
                break
            await asyncio.sleep(0.5)

        if result is None:
            raise RuntimeError("All Gemini API keys exhausted or failed")
        all_embeddings.extend(result)

    return all_embeddings


async def embed_query(text: str) -> list[float]:
    results = await embed_texts([text], task_type="RETRIEVAL_QUERY")
    return results[0]
