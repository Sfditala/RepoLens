# الإعدادات: بتقرأ القيم من ملف .env (اسم الموديل، لغة التقرير، عدد الـ commits، عدد ملفات الكود، ...).
#
# 📝 نوتات تعلّمتها:
# - اسم الحقل = اسم المتغير بالـ .env بدون الـ prefix وبأحرف صغيرة
#     max_commits  <->  REPOLENS_MAX_COMMITS
# - ⚠️ غلطة صارت معي: سمّيت الحقل commits_count، فصار يدوّر على REPOLENS_COMMITS_COUNT
#     فالقيمة بالـ .env انتجاهلت بصمت وأخد الافتراضي -> bug ساكت بدون أي خطأ.
# - قيمة من نوع غلط (مثلاً REPOLENS_MAX_COMMITS=abc) -> ValidationError، مش تجاهل.
#     وهاد منيح: الخطأ بيطلع من أول البرنامج بدل ما يخرب بعدين بمكان بعيد.
# - extra="ignore" بيتجاهل بس المتغيرات اللي ما إلها حقل أصلاً.
# - متغير مش موجود بالـ .env -> بياخد القيمة الافتراضية (= 20).
#
# - provider: مين الموديل؟ gemini أو anthropic. "auto" = حسب أي مفتاح موجود بالـ .env.
#     بفضل LangChain باقي المشروع ما بيعرف مين الموديل، التبديل كله بـ llm.py.
from typing import Literal
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",          # من وين نقرأ
        env_prefix="REPOLENS_",   # بيتحط قبل اسم كل حقل -> بيمنع التضارب مع متغيرات تانية بالجهاز
        extra="ignore",           # متغير بالـ .env ما إله حقل -> تجاهله
    )
    provider: Literal["auto", "gemini", "anthropic"] = "auto"
    # validation_alias: هدول بدنا ياهم بدون prefix، لأن أساميهم الرسمية هيك
    google_api_key: str = Field(default="", validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"))
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    gemini_model: str = "gemini-3.5-flash"
    # إذا الموديل الأساسي مضغوط (503) أو خلصت حصته، منجرّب هاد (فاضي = بدون بديل)
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    anthropic_model: str = "claude-opus-5-5"
    report_lang: Literal["en", "ar"] = "ar"   # Literal: بس هالقيم مسموحة، غيرها -> خطأ (الترتيب ما بيفرق)
    max_commits: int = 20
    max_code_files: int = 5
    max_lines_per_file: int = 150
    # قديش الموديل "بيفكّر" قبل ما يجاوب (low | medium | high | xhigh | max)
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    # إذا الموديل رفض الطلب لأسباب أمان، الـ API بيعيد الطلب على موديل بديل تلقائياً
    refusal_fallback: bool = True  # Claude بس
    # حد الطلبات بالدقيقة (0 = بلا حد). الـ free tier تبع Gemini بيسمح بـ 5 بالدقيقة بس
    requests_per_minute: int = 0

    def resolved_provider(self) -> Literal["gemini", "anthropic"]:
        if self.provider != "auto":
            return self.provider
        if self.google_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        return "gemini"

    def resolved_model(self) -> str:
        return self.gemini_model if self.resolved_provider() == "gemini" else self.anthropic_model


# object واحد، وباقي الملفات بتعمل: from repolens.config import settings
settings = Settings()
