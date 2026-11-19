# نماذج Pydantic:
# - RepoSnapshot: كل المعلومات اللي قرأناها من الريبو (README، شجرة الملفات، الـ commits، عينات الكود، ...)
# - Finding / SectionResult: نتيجة تقييم قسم واحد (درجة + مشاكل مع الدليل + اقتراحات)
# - Report: التقرير النهائي (الدرجة الكلية + الأقسام + خطة التحسين)
#
# 📝 نوتات تعلّمتها:
# - هدول "قوالب بيانات" (متل استمارة فاضية)، مش "آباء" للوراثة.
#     الكود بيعبّيهم: RepoSnapshot(url=..., readme=...)  -> علاقة "بيستخدم"، مش "بيرث من".
#     الوراثة الوحيدة هون: كلهم بيرثوا من BaseModel، وهاد اللي بيعطيهم الـ validation.
# - default_factory=list -> دالة بتنستدعى مع كل object جديد، فكل object إله قائمته لحاله.
#     ببايثون العادي "= []" بتتشارك بين الكل (bug: mutable default argument).
#     Pydantic بينسخها فكانت رح تزبط، بس default_factory هي العادة الصح بكل مكان.
# - Field(ge=0, le=10): ge = أكبر أو يساوي، le = أصغر أو يساوي.
#     جربت score=15 -> ValidationError: Input should be less than or equal to 10 ✅
# - description="..." بيوصل للـ LLM كشرح للحقل (تعليمات صغيرة للموديل) -> لهيك بالإنجليزي.
# - str | None = None: الحقل ممكن يكون فاضي (مثلاً ريبو بدون README).
# - ⚠️ غلطة صارت معي: نسيت has_requirements بـ RepoSnapshot -> ضفته.

from typing import Literal
from pydantic import BaseModel, Field


class CodeSample(BaseModel):
    path: str
    lines: int
    content: str


class RepoSnapshot(BaseModel):
    url: str
    readme: str | None = None
    file_tree: list[str] = Field(default_factory=list)
    has_tests_dir: bool = False
    has_requirements: bool = False
    has_gitignore: bool = False
    commit_messages: list[str] = Field(default_factory=list)
    code_samples: list[CodeSample] = Field(default_factory=list)


class Finding(BaseModel):
    issue: str = Field(description="The problem found, in one short sentence")
    evidence: str = Field(
        description="Where it was found: a file name, line count, or commit message"
    )
    severity: Literal["high", "medium", "low"] = Field(
        description="How much this hurts the repo's impression on a recruiter"
    )


# الشكل اللي بنطلبه من الـ LLM (structured output). كل الحقول مطلوبة وبدون حدود رقمية،
# لأن الـ structured outputs تبع Claude ما بتدعم minimum/maximum. الحدود بنفرضها بـ SectionResult.
class SectionAssessment(BaseModel):
    score: int = Field(description="Score for this section, an integer from 0 to 10")
    summary: str = Field(description="One or two sentences on the overall state of this section")
    findings: list[Finding] = Field(description="Concrete problems with evidence, most important first")
    suggestions: list[str] = Field(description="Concrete, actionable improvements, most important first")


class SectionResult(BaseModel):
    area: str
    score: int = Field(ge=0, le=10, description="Score for this section from 0 to 10")
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class Report(BaseModel):
    repo_url: str
    lang: Literal["ar", "en"] = "ar"
    overall_score: float = Field(ge=0, le=10)
    sections: list[SectionResult]
    improvement_plan: list[str]
    # أقسام ما قدرنا نقيّمها (مثلاً الموديل ما رد)، والدرجة الكلية محسوبة بدونها
    failed_areas: list[str] = Field(default_factory=list)
