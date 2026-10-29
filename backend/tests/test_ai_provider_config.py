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


def test_current_frontend_origin_is_allowed_even_when_render_has_stale_origins():
    settings = Settings(ALLOWED_ORIGINS="https://rivu-ai-murex.vercel.app")
    assert "https://rivu-ai-woad.vercel.app" in settings.ALLOWED_ORIGINS_LIST
