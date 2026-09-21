import json

import requests
from django.conf import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SUPPORT_SYSTEM_PROMPT = (
    "You are SupportAI, a helpful customer support assistant. "
    "Answer clearly and concisely. If you are unsure, say so."
)


def chat_completion(messages: list[dict], *, system_prompt: str | None = SUPPORT_SYSTEM_PROMPT) -> str:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend(messages)

    response = requests.post(
        url=OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "X-OpenRouter-Title": "SupportAI",
        },
        data=json.dumps({
            "model": settings.OPENROUTER_MODEL,
            "messages": payload_messages,
        }),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def chat_completion_or_none(messages: list[dict], *, system_prompt: str | None = SUPPORT_SYSTEM_PROMPT) -> str | None:
    try:
        return chat_completion(messages, system_prompt=system_prompt)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            return None
        raise
