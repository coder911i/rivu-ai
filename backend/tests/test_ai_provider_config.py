"""Provider configuration must fail clearly for adapters not implemented yet."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("provider", ["openai", "gemini", "unknown", ""])
def test_unsupported_provider_is_rejected_at_settings_initialization(provider):
    with pytest.raises(ValidationError, match="Rivu currently supports only 'groq'"):
        Settings(DEFAULT_AI_PROVIDER=provider)


def test_groq_is_the_supported_provider():
    assert Settings(DEFAULT_AI_PROVIDER="Groq").DEFAULT_AI_PROVIDER == "groq"
