# المنسّق: بيربط كل شي ببعض
# تنزيل الريبو -> بناء RepoSnapshot -> تشغيل كل التقييمات بنفس الوقت (async) -> حساب الدرجة الكلية وخطة التحسين -> Report
#
# 📝 نوتات:
# - asyncio.gather: بيشغّل الـ 4 تقييمات بنفس الوقت. كل واحد بيستنى رد الـ LLM،
#     وبدل ما نستنى 4 مرات ورا بعض (مجموع الوقت)، منستنى مرة وحدة تقريباً (أطول واحد).
# - asyncio.to_thread: التنزيل والقراءة كود عادي (مش async)، فمنشغّله بـ thread
#     عشان ما يوقف الـ event loop.
# - return_exceptions=True: إذا قسم واحد فشل، منطلّع تقرير بالباقي (failed_areas) بدل ما يفشل كل شي.
# - normalize_url: ما منعمل clone إلا لروابط github.com، وهيك ما حدا بيقدر يخلينا
#     ننزّل مسار محلي أو بروتوكول غريب.
import asyncio
import logging
import re
import shutil
from collections.abc import Sequence

from repolens.config import settings
from repolens.core import github_api
from repolens.core.readers import build_snapshot
from repolens.core.repo_loader import cloned_repo
from repolens.evaluators import BaseEvaluator, default_evaluators
from repolens.llm import get_chat_model
from repolens.models import Report, RepoSnapshot, SectionResult

logger = logging.getLogger(__name__)

WEIGHTS = {"readme": 0.30, "structure": 0.30, "tests": 0.20, "commits": 0.20}
PLAN_LENGTH = 5

_NAME = r"[A-Za-z0-9._-]+"
_REPO_PATH = re.compile(rf"^(?:https?://)?(?:www\.)?github\.com/({_NAME})/({_NAME})(?:/.*)?$", re.IGNORECASE)
_SHORTHAND = re.compile(rf"^({_NAME})/({_NAME})$")


class InvalidRepoUrlError(ValueError):
    """Raised when the input is not a public GitHub repository URL."""


def normalize_url(raw: str) -> str:
    text = raw.strip().split("?")[0].split("#")[0].rstrip("/")
    match = _REPO_PATH.match(text) or _SHORTHAND.match(text)
    if not match:
        raise InvalidRepoUrlError(
            f"'{raw}' is not a GitHub repository. Use https://github.com/<user>/<repo> or <user>/<repo>."
        )
    owner, repo = match.groups()
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner in {".", ".."} or repo in {"", ".", ".."}:
        raise InvalidRepoUrlError(f"'{raw}' is not a valid repository name.")
    return f"https://github.com/{owner}/{repo}"


def use_git() -> bool:
    if settings.repo_source == "auto":
        return shutil.which("git") is not None
    return settings.repo_source == "git"


def collect_snapshot(url: str) -> RepoSnapshot:
    if use_git():
        with cloned_repo(url) as root:
            return build_snapshot(url, root)
    # بدون git (مثلاً على Vercel): tarball + commits من GitHub API
    commits = github_api.fetch_commit_messages(url, settings.max_commits)
    with github_api.downloaded_repo(url) as root:
        return build_snapshot(url, root, commit_messages=commits)


def overall_score(sections: Sequence[SectionResult]) -> float:
    total_weight = sum(WEIGHTS.get(s.area, 0.0) for s in sections)
    if total_weight == 0:
        return 0.0
    weighted = sum(s.score * WEIGHTS.get(s.area, 0.0) for s in sections)
    return round(weighted / total_weight, 1)


def improvement_plan(sections: Sequence[SectionResult], limit: int = PLAN_LENGTH) -> list[str]:
    # أضعف قسم أولاً، وبناخد أهم اقتراح من كل قسم بالدور (round-robin) لحتى نوصل للحد
    ordered = sorted(sections, key=lambda s: (s.score, -WEIGHTS.get(s.area, 0.0)))
    plan: list[str] = []
    depth = max((len(s.suggestions) for s in ordered), default=0)
    for i in range(depth):
        for section in ordered:
            if i < len(section.suggestions) and section.score < 10:
                step = section.suggestions[i].strip()
                if step and step not in plan:
                    plan.append(step)
                if len(plan) == limit:
                    return plan
    return plan


async def evaluate_snapshot(
    snapshot: RepoSnapshot,
    evaluators: Sequence[BaseEvaluator] | None = None,
    lang: str | None = None,
) -> Report:
    lang = lang or settings.report_lang
    evaluators = list(evaluators) if evaluators is not None else default_evaluators()
    results = await asyncio.gather(
        *(e.evaluate(snapshot, lang) for e in evaluators), return_exceptions=True
    )
    sections = [r for r in results if isinstance(r, SectionResult)]
    failed = [e.area for e, r in zip(evaluators, results) if isinstance(r, BaseException)]
    for e, r in zip(evaluators, results):
        if isinstance(r, BaseException):
            logger.warning("%s evaluation failed: %s", e.area, r)
    if not sections:
        # ولا قسم نجح -> ما في تقرير، منرمي أول خطأ
        raise next(r for r in results if isinstance(r, BaseException))
    return Report(
        repo_url=snapshot.url,
        lang=lang,
        overall_score=overall_score(sections),
        sections=sections,
        improvement_plan=improvement_plan(sections),
        failed_areas=failed,
    )


async def analyze(
    raw_url: str,
    lang: str | None = None,
    evaluators: Sequence[BaseEvaluator] | None = None,
) -> Report:
    url = normalize_url(raw_url)
    if evaluators is None:
        get_chat_model()  # بيفشل فوراً إذا ما في API key، قبل ما نضيّع وقت على التنزيل
    snapshot = await asyncio.to_thread(collect_snapshot, url)
    return await evaluate_snapshot(snapshot, evaluators, lang)
