"""
Thin wrapper around the Groq API (OpenAI-compatible chat completions).
Centralizing this means stage modules don't care which SDK/provider is used.
"""
import json
import re
from groq import Groq
from app.config import get_settings

settings = get_settings()
_client = Groq(api_key=settings.groq_api_key)


def _strip_json_fences(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json ... ``` fences despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def chat(
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Plain text completion."""
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
    """
    Completion that must return JSON. We instruct the model explicitly and
    additionally pass response_format for Groq's JSON mode where supported.
    """
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
    raw = response.choices[0].message.content
    cleaned = _strip_json_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq did not return valid JSON: {e}\nRaw: {raw[:500]}")
