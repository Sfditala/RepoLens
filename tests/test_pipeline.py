# اختبارات الـ pipeline والقراءة بدون LLM: باستخدام تقييمات وهمية (fake evaluators) وريبو محلي صغير.
import subprocess
from pathlib import Path

import pytest

from repolens.core.readers import build_snapshot, read_lines, walk_files
from repolens.evaluators import ReadmeEvaluator, TestsEvaluator
from repolens.evaluators.base import BaseEvaluator
from repolens.models import Finding, RepoSnapshot, SectionAssessment, SectionResult
from repolens.pipeline import (
    InvalidRepoUrlError,
    evaluate_snapshot,
    improvement_plan,
    normalize_url,
    overall_score,
)
from repolens.report import render_markdown, render_text


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def local_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "node_modules" / "lib").mkdir(parents=True)

    (repo / "README.md").write_text("# Demo\n\nRun with `python -m app`.\n", encoding="utf-8")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("pydantic\n", encoding="utf-8")
    (repo / "app" / "main.py").write_text("\n".join(f"x{i} = {i}" for i in range(300)), encoding="utf-8")
    (repo / "app" / "util.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "tests" / "test_util.py").write_text("def test_add():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    (repo / "node_modules" / "lib" / "index.js").write_text("module.exports = 1\n", encoding="utf-8")

    git(repo, "init", "-q")
    git(repo, "add", "README.md", ".gitignore", "requirements.txt")
    git(repo, "commit", "-q", "-m", "Add README and project setup")
    git(repo, "add", "app", "tests")
    git(repo, "commit", "-q", "-m", "Add util module with tests")
    return repo


# ---------- readers ----------

def test_walk_files_skips_ignored_dirs(local_repo):
    files = {p.as_posix() for p in walk_files(local_repo)}
    assert "app/main.py" in files
    assert "tests/test_util.py" in files
    assert not any(f.startswith(("node_modules/", ".git/")) for f in files)


def test_walk_files_is_a_one_shot_generator(local_repo):
    gen = walk_files(local_repo)
    assert len(list(gen)) > 0
    assert list(gen) == []


def test_read_lines_stops_at_limit(local_repo):
    lines = list(read_lines(local_repo / "app" / "main.py", 10))
    assert len(lines) == 10
    assert lines[0] == "x0 = 0"


def test_build_snapshot_collects_everything(local_repo, monkeypatch):
    from repolens.config import settings

    monkeypatch.setattr(settings, "max_lines_per_file", 50)
    snap = build_snapshot("https://github.com/demo/demo", local_repo)

    assert snap.readme.startswith("# Demo")
    assert snap.has_tests_dir and snap.has_requirements and snap.has_gitignore
    assert snap.commit_messages == ["Add util module with tests", "Add README and project setup"]
    # الكود الرئيسي: الأكبر أولاً، والاختبارات مش من العينات
    assert [s.path for s in snap.code_samples] == ["app/main.py", "app/util.py"]
    assert snap.code_samples[0].lines == 300
    assert len(snap.code_samples[0].content.splitlines()) == 50


# ---------- URL validation ----------

@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/pallets/click",
        "https://github.com/pallets/click/",
        "https://github.com/pallets/click.git",
        "http://www.github.com/pallets/click",
        "github.com/pallets/click",
        "pallets/click",
        "https://github.com/pallets/click/tree/main/src",
        "  https://github.com/pallets/click?tab=readme  ",
    ],
)
def test_normalize_url_accepts_github_forms(raw):
    assert normalize_url(raw) == "https://github.com/pallets/click"


@pytest.mark.parametrize(
    "raw",
    ["", "click", "https://gitlab.com/a/b", "file:///etc/passwd", "C:/repo", "https://github.com/onlyuser", "ext::sh -c x"],
)
def test_normalize_url_rejects_other_input(raw):
    with pytest.raises(InvalidRepoUrlError):
        normalize_url(raw)


# ---------- scoring and plan ----------

def section(area, score, suggestions=()):
    return SectionResult(area=area, score=score, suggestions=list(suggestions))


def test_overall_score_is_weighted():
    sections = [section("readme", 10), section("structure", 10), section("tests", 0), section("commits", 0)]
    assert overall_score(sections) == 6.0


def test_overall_score_with_no_sections():
    assert overall_score([]) == 0.0


def test_improvement_plan_starts_with_weakest_area():
    sections = [
        section("readme", 8, ["Add screenshots"]),
        section("tests", 1, ["Add pytest tests", "Add CI"]),
        section("commits", 5, ["Write descriptive messages"]),
    ]
    plan = improvement_plan(sections, limit=3)
    assert plan == ["Add pytest tests", "Write descriptive messages", "Add screenshots"]


# ---------- evaluators with a fake LLM ----------

class FakeEvaluator(BaseEvaluator):
    def __init__(self, area: str, score: int):
        super().__init__()
        self.area = area
        self._score = score

    def build_prompt(self, snapshot):
        return ""

    async def evaluate(self, snapshot, lang="ar"):
        return SectionResult(area=self.area, score=self._score, suggestions=[f"improve {self.area}"])


@pytest.mark.asyncio
async def test_evaluate_snapshot_builds_report():
    snap = RepoSnapshot(url="https://github.com/demo/demo")
    evaluators = [FakeEvaluator("readme", 8), FakeEvaluator("structure", 6), FakeEvaluator("tests", 2), FakeEvaluator("commits", 4)]
    report = await evaluate_snapshot(snap, evaluators, lang="en")

    assert report.lang == "en"
    assert [s.area for s in report.sections] == ["readme", "structure", "tests", "commits"]
    assert report.overall_score == 5.4
    assert report.improvement_plan[0] == "improve tests"


@pytest.mark.asyncio
async def test_base_evaluator_uses_llm_result_and_clamps_score():
    seen = {}

    async def fake_ask(system, prompt, schema):
        seen["system"], seen["prompt"], seen["schema"] = system, prompt, schema
        return SectionAssessment(
            score=14,
            summary="ok",
            findings=[Finding(issue="No install steps", evidence="README.md", severity="high")],
            suggestions=["Add an Installation section"],
        )

    snap = RepoSnapshot(url="https://github.com/demo/demo", readme="# Demo", file_tree=["README.md"])
    result = await ReadmeEvaluator(ask=fake_ask).evaluate(snap, lang="en")

    assert result.area == "readme"
    assert result.score == 10
    assert result.findings[0].evidence == "README.md"
    assert seen["schema"] is SectionAssessment
    assert "<repo_data>" in seen["prompt"] and "# Demo" in seen["prompt"]
    assert "English" in seen["system"]


def test_tests_evaluator_prompt_counts_files():
    snap = RepoSnapshot(
        url="u",
        file_tree=["app/main.py", "app/util.py", "tests/test_util.py", ".github/workflows/ci.yml"],
        has_tests_dir=True,
    )
    prompt = TestsEvaluator(ask=None).build_prompt(snap)
    assert "source code files: 2" in prompt
    assert "test files: 1" in prompt
    assert ".github/workflows/ci.yml" in prompt


def test_base_evaluator_is_abstract():
    with pytest.raises(TypeError):
        BaseEvaluator()


# ---------- report ----------

def test_render_text_and_markdown():
    from repolens.models import Report

    report = Report(
        repo_url="https://github.com/demo/demo",
        lang="ar",
        overall_score=6.0,
        sections=[
            SectionResult(
                area="tests",
                score=2,
                summary="ما في اختبارات",
                findings=[Finding(issue="ما في مجلد tests", evidence="file tree", severity="high")],
            )
        ],
        improvement_plan=["أضيفي اختبارات pytest"],
    )
    text = render_text(report)
    assert "الدرجة: 6/10" in text
    assert "الاختبارات: 2/10" in text
    assert "1) أضيفي اختبارات pytest" in text
    assert "## الاختبارات — 2/10" in render_markdown(report)


class FailingEvaluator(FakeEvaluator):
    async def evaluate(self, snapshot, lang="ar"):
        raise RuntimeError("503 UNAVAILABLE")


@pytest.mark.asyncio
async def test_partial_failure_still_returns_report():
    snap = RepoSnapshot(url="https://github.com/demo/demo")
    report = await evaluate_snapshot(snap, [FakeEvaluator("readme", 8), FailingEvaluator("tests", 0)], lang="en")
    assert [s.area for s in report.sections] == ["readme"]
    assert report.failed_areas == ["tests"]
    assert report.overall_score == 8.0
    assert "Could not evaluate: Tests" in render_text(report)


@pytest.mark.asyncio
async def test_all_failed_raises():
    snap = RepoSnapshot(url="https://github.com/demo/demo")
    with pytest.raises(RuntimeError, match="503"):
        await evaluate_snapshot(snap, [FailingEvaluator("readme", 0)], lang="en")
