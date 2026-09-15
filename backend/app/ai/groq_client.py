"""Groq AI provider implementation."""

import time
import json
from typing import Any
import structlog

from app.ai.base import AIProvider, AIMessage, AIResponse
from app.core.config import settings
from app.core.exceptions import AIError

logger = structlog.get_logger(__name__)


class GroqProvider(AIProvider):
    """Groq API provider using llama-3.3-70b-versatile."""

    def __init__(self):
        if not settings.GROQ_API_KEY:
            logger.warning("groq_api_key_missing", msg="GROQ_API_KEY not set — AI features will be limited")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            except ImportError:
                raise AIError("groq package not installed. Run: pip install groq")
        return self._client

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return settings.GROQ_MODEL

    async def complete(
        self,
        messages: list[AIMessage],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: str | None = None,
    ) -> AIResponse:
        if not settings.GROQ_API_KEY:
            raise AIError("GROQ_API_KEY is not configured")

        client = self._get_client()
        start = time.perf_counter()

        groq_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": groq_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)
            latency_ms = round((time.perf_counter() - start) * 1000)

            content = response.choices[0].message.content or ""
            usage = response.usage

            logger.info(
                "groq_complete",
                model=self.model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
            )

            return AIResponse(
                content=content,
                model=self.model,
                provider="groq",
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error("groq_error", error=str(e))
            raise AIError(f"Groq API error: {e}") from e
