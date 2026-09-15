"""
AI Provider Abstraction — allows swapping Groq/OpenAI/Gemini/local.
All providers must implement the AIProvider interface.
"""

from abc import ABC, abstractmethod
from typing import Any
import structlog

logger = structlog.get_logger(__name__)


class AIMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class AIResponse:
    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms


class AIProvider(ABC):
    """Abstract AI provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[AIMessage],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: str | None = None,
    ) -> AIResponse:
        ...

    async def complete_json(
        self,
        messages: list[AIMessage],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Request a JSON-mode response."""
        return await self.complete(
            messages, temperature=temperature, max_tokens=max_tokens, response_format="json_object"
        )
