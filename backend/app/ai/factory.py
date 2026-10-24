"""
AI provider factory — returns the configured provider.
Groq is currently the supported provider.
"""

from app.ai.base import AIProvider
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

SUPPORTED_AI_PROVIDERS = ("groq",)
UNSUPPORTED_AI_PROVIDERS = ("openai", "gemini")

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """Get the configured AI provider (singleton)."""
    global _provider
    if _provider is None:
        provider_name = settings.DEFAULT_AI_PROVIDER.lower()
        if provider_name == "groq":
            from app.ai.groq_client import GroqProvider
            _provider = GroqProvider()
        elif provider_name in UNSUPPORTED_AI_PROVIDERS:
            raise ValueError(
                f"AI provider '{provider_name}' is not supported. Currently, only 'groq' is supported."
            )
        else:
            raise ValueError(
                f"Unsupported AI provider '{provider_name}'. Currently, only 'groq' is supported."
            )
        logger.info("ai_provider_initialized", provider=provider_name)
    return _provider


def reset_ai_provider() -> None:
    """Reset the cached AI provider instance (for testing)."""
    global _provider
    _provider = None
