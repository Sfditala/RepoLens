# Context manager: بينزّل الريبو (git clone) بمجلد مؤقت، وبيحذفه تلقائياً لما نخلص حتى لو صار خطأ.
#
# 📝 نوتات تعلّمتها:
# - context manager = with: بيعمل setup بالدخول وتنضيف بالطلوع، متل with open(...).
# - @contextmanager + yield:
#     قبل الـ yield -> بالدخول (التنزيل)، yield dest -> بيعطي القيمة لـ "as"، بعد الـ yield -> بالطلوع (التنضيف).
# - جربت 1/0 جوّا الـ with -> المجلد انمسح رغم الخطأ ✅، بس الخطأ نفسه ضل وطلع لفوق.
#     يعني with = متل try/finally: بينضّف دايماً، بس ما بيبلع الخطأ.
# - TemporaryDirectory هو كمان context manager -> with جوّا with، والداخلي بيمسح المجلد.
# - class RepoCloneError(Exception): خطأ خاص فينا (أول وراثة بالمشروع) -> منقدر نمسكه لحاله.
#     جربت رابط مش موجود -> RepoCloneError مع رسالة git "Repository not found" 💥
#     وما انمسك لأن الـ except كان بس لـ ZeroDivisionError -> except بتمسك بس النوع اللي بتسميه.
# - subprocess.run([...]) بقائمة مش نص -> أأمن، الرابط ما بيتنفّذ كأمر.
#     returncode == 0 يعني نجح، غير هيك فشل، والسبب بـ stderr.
# - --depth = آخر N commits بس -> أسرع.
# - Path(tmp) / "repo": الـ / هون بتركّب مسار، مش قسمة.
# - ⚠️ غلطة صارت معي: استخدمت Settings (الـ class) بدل settings (الـ object):
#     Settings().max_commits -> بيقرأ .env من جديد كل مرة، والتغيير بالاختبارات ما بيوصل.
#     Settings.max_commits   -> AttributeError، لأن القيم بتعيش بالـ object مش بالـ class (استمارة فاضية).
#     الصح: from repolens.config import settings  ثم settings.max_commits
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from repolens.config import settings


class RepoCloneError(Exception):
    """Raised when git clone fails."""

    pass


@contextmanager
def cloned_repo(url: str):
    with tempfile.TemporaryDirectory(prefix="repolens_") as tmp:
        dest = Path(tmp) / "repo"
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", str(settings.max_commits), "--", url, str(dest)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                # ريبو خاص أو مش موجود: بدون هاد git بيوقف يستنى username/password للأبد
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except subprocess.TimeoutExpired as exc:
            raise RepoCloneError(f"Cloning {url} took too long (over 2 minutes)") from exc
        if result.returncode != 0:
            raise RepoCloneError(f"Failed to clone {url}: {result.stderr.strip()}")

        yield dest
