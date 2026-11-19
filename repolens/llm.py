# LangChain: بيجهّز الموديل (Gemini أو Claude) وبيربطه بـ schema من Pydantic
# عن طريق with_structured_output، عشان يرجع الجواب كـ object منظم مش نص حر.
#
# 📝 نوتات:
# - هون بس منعرف مين المزوّد. باقي المشروع بيستدعي ask_structured وبس،
#     وهاي فايدة LangChain: ChatGoogleGenerativeAI و ChatAnthropic إلهم نفس الواجهة.
# - method="json_schema" = الـ structured output الرسمي عند الاتنين.
#     (عند Claude الطريقة الافتراضية function_calling بتجبر الموديل يستدعي tool،
#     وهاد ممنوع على claude-opus-5-5 وبيرجع 400.)
# - ما منبعت temperature، بدلها منتحكم بـ effort (عند Gemini اسمه thinking_level).
# - lru_cache: منعمل الموديل مرة وحدة بس ومنعيد استخدامه (ومعه نفس الـ rate limiter).
# - REPOLENS_REQUESTS_PER_MINUTE: Gemini المجاني بيسمح 5 طلبات بالدقيقة. جربنا بدونه -> 429 RESOURCE_EXHAUSTED.
# - with_fallbacks: Gemini رجّع 503 (high demand) بالتجربة، فصار في موديل بديل (flash-lite).
# - الـ imports تبع langchain جوّا الـ functions: تقيلة وبتاخد ثواني،
#     فالاختبارات والأخطاء السريعة ما بتستناها.
from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel

from repolens.config import settings

T = TypeVar("T", bound=BaseModel)

# Gemini بيدعم لحد high بس
GEMINI_EFFORT = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


def _rate_limiter() -> Any:
    # rate limiter من LangChain: بيخلي الطلبات تستنى دورها بدل ما نتجاوز الحد ونوكل 429
    if settings.requests_per_minute <= 0:
        return None
    from langchain_core.rate_limiters import InMemoryRateLimiter

    return InMemoryRateLimiter(
        requests_per_second=settings.requests_per_minute * 0.9 / 60,  # 10% هامش أمان
        check_every_n_seconds=0.2,
        max_bucket_size=1,
    )


class MissingApiKeyError(RuntimeError):
    """Raised when the API key for the selected provider is not configured."""


def _gemini_model(model_name: str | None = None) -> Any:
    if not settings.google_api_key:
        raise MissingApiKeyError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and put your Google AI Studio key in it."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model_name or settings.gemini_model,
        google_api_key=settings.google_api_key,
        thinking_level=GEMINI_EFFORT[settings.effort],
        max_retries=1,
        timeout=180,
        rate_limiter=_rate_limiter(),
    )


def _anthropic_model() -> Any:
    if not settings.anthropic_api_key:
        raise MissingApiKeyError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and put your key in it."
        )
    from langchain_anthropic import ChatAnthropic

    extra: dict = {}
    if settings.refusal_fallback:
        # إذا انرفض الطلب، الـ API بيعيده على موديل بديل لحاله (fallbacks: "default")
        extra = {
            "betas": ["server-side-fallback-2026-07-01"],
            "model_kwargs": {"fallbacks": "default"},
        }
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        max_tokens=16000,
        effort=settings.effort,
        max_retries=2,
        timeout=180,
        rate_limiter=_rate_limiter(),
        **extra,
    )


@lru_cache(maxsize=1)
def get_chat_model() -> Any:
    if settings.resolved_provider() == "gemini":
        return _gemini_model()
    return _anthropic_model()


@lru_cache(maxsize=1)
def get_fallback_model() -> Any | None:
    if settings.resolved_provider() == "gemini" and settings.gemini_fallback_model:
        return _gemini_model(settings.gemini_fallback_model)
    return None


async def ask_structured(system: str, prompt: str, schema: type[T]) -> T:
    model = get_chat_model().with_structured_output(schema, method="json_schema")
    fallback = get_fallback_model()
    if fallback is not None:
        # with_fallbacks من LangChain: إذا الأساسي فشل (مثلاً 503 high demand) بيجرّب البديل لحاله
        model = model.with_fallbacks([fallback.with_structured_output(schema, method="json_schema")])
    result = await model.ainvoke([("system", system), ("human", prompt)])
    if result is None:
        # الموديل ما رجّع JSON صالح -> منرمي خطأ عشان @retry يعيد المحاولة
        raise ValueError(f"The model returned no structured output for {schema.__name__}")
    return result
