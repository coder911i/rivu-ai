"""Tests for AI provider configuration and factory behavior."""

import pytest
from pydantic import ValidationError

from app.ai.factory import get_ai_provider, reset_ai_provider
from app.ai.groq_client import GroqProvider
from app.core.config import Settings
from app.core.exceptions import AIError


@pytest.fixture(autouse=True)
def cleanup_provider():
    """Ensure singleton provider is reset before and after each test."""
    reset_ai_provider()
    yield
    reset_ai_provider()


def test_default_ai_provider_is_groq():
    """Verify that the default configured provider is groq."""
    settings = Settings()
    assert settings.DEFAULT_AI_PROVIDER == "groq"


def test_supported_groq_provider_normalization():
    """Verify that case variations and whitespace for groq are normalized."""
    assert Settings(DEFAULT_AI_PROVIDER="groq").DEFAULT_AI_PROVIDER == "groq"
    assert Settings(DEFAULT_AI_PROVIDER="GROQ").DEFAULT_AI_PROVIDER == "groq"
    assert Settings(DEFAULT_AI_PROVIDER="  groq  ").DEFAULT_AI_PROVIDER == "groq"


def test_unsupported_openai_rejected_during_configuration():
    """Verify that selecting openai is rejected at configuration time."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEFAULT_AI_PROVIDER="openai")

    error_msg = str(exc_info.value)
    assert "AI provider 'openai' is not supported" in error_msg
    assert "only 'groq' is supported" in error_msg


def test_unsupported_openai_case_insensitive_rejection():
    """Verify that case variations of openai are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEFAULT_AI_PROVIDER="OpenAI")

    error_msg = str(exc_info.value)
    assert "AI provider 'openai' is not supported" in error_msg


def test_unsupported_gemini_rejected_during_configuration():
    """Verify that selecting gemini is rejected at configuration time."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEFAULT_AI_PROVIDER="gemini")

    error_msg = str(exc_info.value)
    assert "AI provider 'gemini' is not supported" in error_msg
    assert "only 'groq' is supported" in error_msg


def test_unsupported_gemini_case_insensitive_rejection():
    """Verify that case variations of gemini are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEFAULT_AI_PROVIDER="Gemini")

    error_msg = str(exc_info.value)
    assert "AI provider 'gemini' is not supported" in error_msg


def test_unknown_provider_rejected_during_configuration():
    """Verify that arbitrary unsupported providers are rejected at configuration time."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEFAULT_AI_PROVIDER="anthropic")

    error_msg = str(exc_info.value)
    assert "Unsupported AI provider 'anthropic'" in error_msg
    assert "only 'groq' is supported" in error_msg


def test_empty_provider_rejected_during_configuration():
    """Verify that an empty provider string is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEFAULT_AI_PROVIDER="")

    assert "Unsupported AI provider ''" in str(exc_info.value)


def test_environment_variable_unsupported_provider_rejected(monkeypatch):
    """Verify that setting DEFAULT_AI_PROVIDER via environment variables fails on configuration load."""
    monkeypatch.setenv("DEFAULT_AI_PROVIDER", "openai")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "AI provider 'openai' is not supported" in str(exc_info.value)

    monkeypatch.setenv("DEFAULT_AI_PROVIDER", "gemini")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "AI provider 'gemini' is not supported" in str(exc_info.value)


def test_get_ai_provider_returns_groq_singleton():
    """Verify that the factory returns a GroqProvider singleton for groq."""
    provider = get_ai_provider()
    assert isinstance(provider, GroqProvider)
    assert provider.name == "groq"

    # Subsequent call returns the identical singleton instance
    provider_second = get_ai_provider()
    assert provider_second is provider


def test_factory_rejects_unsupported_openai_without_not_implemented_error(monkeypatch):
    """Verify that the factory raises ValueError (not NotImplementedError) for openai."""
    from app.core import config

    monkeypatch.setattr(config.settings, "DEFAULT_AI_PROVIDER", "openai")
    with pytest.raises(ValueError) as exc_info:
        get_ai_provider()

    assert not issubclass(exc_info.type, NotImplementedError)
    assert "AI provider 'openai' is not supported" in str(exc_info.value)
    assert "only 'groq' is supported" in str(exc_info.value)


def test_factory_rejects_unsupported_gemini_without_not_implemented_error(monkeypatch):
    """Verify that the factory raises ValueError (not NotImplementedError) for gemini."""
    from app.core import config

    monkeypatch.setattr(config.settings, "DEFAULT_AI_PROVIDER", "gemini")
    with pytest.raises(ValueError) as exc_info:
        get_ai_provider()

    assert not issubclass(exc_info.type, NotImplementedError)
    assert "AI provider 'gemini' is not supported" in str(exc_info.value)
    assert "only 'groq' is supported" in str(exc_info.value)


def test_factory_rejects_unknown_provider(monkeypatch):
    """Verify that the factory raises ValueError for any unknown provider."""
    from app.core import config

    monkeypatch.setattr(config.settings, "DEFAULT_AI_PROVIDER", "unknown_provider")
    with pytest.raises(ValueError) as exc_info:
        get_ai_provider()

    assert "Unsupported AI provider 'unknown_provider'" in str(exc_info.value)


def test_groq_provider_unconfigured_key_raises_ai_error(monkeypatch):
    """Verify that groq provider without API key raises AIError without external network calls."""
    import asyncio
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", None)
    provider = GroqProvider()
    with pytest.raises(AIError) as exc_info:
        asyncio.run(provider.complete([]))

    assert "GROQ_API_KEY is not configured" in str(exc_info.value)
