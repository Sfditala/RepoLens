# اختبارات اختيار المزوّد (Gemini أو Claude) حسب الإعدادات والمفاتيح.
import pytest

from repolens.config import Settings
from repolens.llm import MissingApiKeyError, _anthropic_model, _gemini_model


def make(**values) -> Settings:
    # _env_file=None: ما منقرأ .env الحقيقي بالاختبار
    return Settings(_env_file=None, **values)


def test_auto_prefers_gemini_when_google_key_is_set():
    s = make(GOOGLE_API_KEY="g", ANTHROPIC_API_KEY="a")
    assert s.resolved_provider() == "gemini"
    assert s.resolved_model() == s.gemini_model


def test_auto_falls_back_to_anthropic():
    s = make(ANTHROPIC_API_KEY="a")
    assert s.resolved_provider() == "anthropic"
    assert s.resolved_model() == s.anthropic_model


def test_explicit_provider_wins():
    s = make(provider="anthropic", GOOGLE_API_KEY="g")
    assert s.resolved_provider() == "anthropic"


def test_gemini_key_alias():
    assert make(GEMINI_API_KEY="g").google_api_key == "g"


@pytest.mark.parametrize("factory", [_gemini_model, _anthropic_model])
def test_missing_key_raises(monkeypatch, factory):
    from repolens import llm

    monkeypatch.setattr(llm, "settings", make())
    with pytest.raises(MissingApiKeyError):
        factory()
