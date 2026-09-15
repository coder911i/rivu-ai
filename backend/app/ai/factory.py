"""
AI provider factory — returns the configured provider.
Easy to swap between Groq, OpenAI, Gemini.
"""

from app.ai.base import AIProvider
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """Get the configured AI provider (singleton)."""
    global _provider
    if _provider is None:
        provider_name = settings.DEFAULT_AI_PROVIDER.lower()
        if provider_name == "groq":
            from app.ai.groq_client import GroqProvider
            _provider = GroqProvider()
        elif provider_name == "openai":
            # Future: from app.ai.openai_client import OpenAIProvider
            raise NotImplementedError("OpenAI provider not yet implemented")
        elif provider_name == "gemini":
            raise NotImplementedError("Gemini provider not yet implemented")
        else:
            raise ValueError(f"Unknown AI provider: {provider_name}")
        logger.info("ai_provider_initialized", provider=provider_name)
    return _provider
