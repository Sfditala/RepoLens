# Generators: بتمشي على ملفات الريبو واحد واحد بدل ما تحمّلهم كلهم بالذاكرة.
# - المرور على شجرة الملفات (مع تجاهل .git و node_modules ...)
# - أخذ عينة من ملفات الكود الرئيسية
# - قراءة آخر 20 رسالة commit
# - تجميع كل هاد بـ RepoSnapshot
#
# 📝 نوتات:
# - generator = function فيها yield: بتعطي نتيجة وحدة كل مرة وبتوقف تستنى الطلب الجاي.
# - الـ generator بينقرأ مرة وحدة بس. بعد ما يخلص، list(gen) تانية بترجع [] فاضية.
#     لهيك بـ build_snapshot منحوّل walk_files لقائمة (sorted) لأنه بدنا نستخدمها كذا مرة.
# - read_lines بيوقف (break) عند الحد، فما منقرأ باقي الملف أبداً حتى لو كان ضخم.
# - yield from x  ==  for item in x: yield item
# - sets {} للثوابت لأن "in" فيها سريع، وأسماء الثوابت بأحرف كبيرة.
import subprocess
from collections.abc import Iterator
from pathlib import Path

from repolens.config import settings
from repolens.models import CodeSample, RepoSnapshot

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".next", "target", "vendor", ".gradle",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".c", ".cpp", ".cs", ".rb", ".php", ".kt", ".swift",
    ".ipynb", ".dart", ".scala", ".vue", ".svelte",
}

TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}
REQUIREMENTS_FILES = {
    "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "environment.yml",
    "package.json", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "Gemfile", "composer.json",
}


def walk_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if path.is_file():
            yield rel


def read_lines(path: Path, limit: int) -> Iterator[str]:
    with path.open(encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            yield line.rstrip("\n")


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def find_readme(root: Path) -> str | None:
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name.lower().startswith("readme"):
            return path.read_text(encoding="utf-8", errors="ignore")
    return None


def is_test_file(rel: Path) -> bool:
    name = rel.name.lower()
    in_test_dir = any(part.lower() in TEST_DIR_NAMES for part in rel.parts[:-1])
    looks_like_test = (
        name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.go"))
    )
    return in_test_dir or looks_like_test


def pick_code_files(root: Path, files: list[Path], limit: int) -> list[Path]:
    # الكود الرئيسي = ملفات كود مش اختبارات، والأكبر أولاً (ملف ضخم بحد ذاته ملاحظة مهمة)
    code_files = [f for f in files if f.suffix in CODE_EXTENSIONS and not is_test_file(f)]
    code_files.sort(key=lambda f: count_lines(root / f), reverse=True)
    return code_files[:limit]


def read_commit_messages(root: Path, limit: int) -> Iterator[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "log", f"-{limit}", "--pretty=format:%s"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    yield from (line for line in result.stdout.splitlines() if line.strip())


def build_snapshot(url: str, root: Path) -> RepoSnapshot:
    files = sorted(walk_files(root))

    samples = []
    for rel in pick_code_files(root, files, settings.max_code_files):
        full = root / rel
        samples.append(
            CodeSample(
                path=rel.as_posix(),
                lines=count_lines(full),
                content="\n".join(read_lines(full, settings.max_lines_per_file)),
            )
        )

    return RepoSnapshot(
        url=url,
        readme=find_readme(root),
        file_tree=[f.as_posix() for f in files],
        has_tests_dir=any(part.lower() in TEST_DIR_NAMES for f in files for part in f.parts[:-1]),
        has_requirements=any(f.name in REQUIREMENTS_FILES for f in files),
        has_gitignore=(root / ".gitignore").is_file(),
        commit_messages=list(read_commit_messages(root, settings.max_commits)),
        code_samples=samples,
    )
