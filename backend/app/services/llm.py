import asyncio
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_clients: list[AsyncOpenAI] = []
_current_index = 0


def _init_clients():
    global _clients
    keys = settings.get_llm_keys()
    _clients = [AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=k) for k in keys]


def _get_client() -> AsyncOpenAI:
    global _current_index
    if not _clients:
        _init_clients()
    if not _clients:
        raise RuntimeError("No LLM API keys configured")
    client = _clients[_current_index % len(_clients)]
    _current_index += 1
    return client


async def chat_completion(messages: list[dict], stream: bool = False, tools: list | None = None):
    if not _clients:
        _init_clients()

    kwargs = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": stream,
        "timeout": 30,
    }
    if tools:
        kwargs["tools"] = tools

    last_error = None

    for attempt in range(len(_clients)):
        client = _get_client()
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "limit" in error_str:
                logger.warning("LLM rate limit hit (key %d), rotating", attempt)
                await asyncio.sleep(0.3)
                continue
            raise

    # All keys exhausted for rate limits — try fallback model with next key
    logger.warning("All LLM keys rate-limited, trying fallback model")
    kwargs["model"] = settings.LLM_FALLBACK_MODEL
    try:
        return await _get_client().chat.completions.create(**kwargs)
    except Exception:
        raise last_error
