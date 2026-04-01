"""DeepSeek chat via OpenAI-compatible API (https://api.deepseek.com)."""
from __future__ import annotations

import os
from typing import Any


def deepseek_settings() -> dict[str, str | None]:
    return {
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def has_deepseek_key() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def chat_completion(
    *,
    system: str,
    user: str,
    max_tokens: int = 500,
    temperature: float = 0.0,
) -> str:
    from openai import OpenAI

    s = deepseek_settings()
    if not s["api_key"]:
        raise ValueError("DEEPSEEK_API_KEY is not set")
    client = OpenAI(api_key=s["api_key"], base_url=s["base_url"])
    r = client.chat.completions.create(
        model=s["model"],
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (r.choices[0].message.content or "").strip()


def langchain_chat_model(**kwargs: Any):
    """ChatOpenAI configured for DeepSeek."""
    from langchain_openai import ChatOpenAI

    s = deepseek_settings()
    return ChatOpenAI(
        model=kwargs.get("model") or s["model"],
        api_key=s["api_key"],
        base_url=s["base_url"],
        temperature=kwargs.get("temperature", 0),
        max_tokens=kwargs.get("max_tokens", 4096),
    )
