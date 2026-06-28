"""
Thin wrapper around the Groq API (OpenAI-compatible chat completions).
Centralizing this means stage modules don't care which SDK/provider is used.

Two clients are exposed:
- chat_json (sync) — used by stages that are otherwise sync (arxiv_search,
  reranker, synthesis), called from the async router via asyncio.to_thread.
- async_chat_json (async) — used by extraction and gap detection, which run
  many concurrent per-paper calls; native async + a semaphore is lighter
  weight than a thread pool for this many I/O-bound calls.
"""
import json
import re
from groq import AsyncGroq, Groq
from app.config import get_settings

settings = get_settings()
_client = Groq(api_key=settings.groq_api_key)
_async_client = AsyncGroq(api_key=settings.groq_api_key)


def _strip_json_fences(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json ... ``` fences despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _parse_json_response(raw: str) -> dict:
    cleaned = _strip_json_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq did not return valid JSON: {e}\nRaw: {raw[:500]}")


def chat(
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Plain text completion (sync)."""
    response = _client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def chat_json(
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict:
    """Completion that must return JSON (sync)."""
    full_system = (
        system
        + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown fences, "
        "no preamble, no explanation outside the JSON object."
    )
    response = _client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return _parse_json_response(response.choices[0].message.content)


async def async_chat_json(
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict:
    """Completion that must return JSON (async) — used for high-concurrency stages."""
    full_system = (
        system
        + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown fences, "
        "no preamble, no explanation outside the JSON object."
    )
    response = await _async_client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return _parse_json_response(response.choices[0].message.content)
