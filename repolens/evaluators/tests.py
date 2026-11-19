# TestsEvaluator: بيقيّم الاختبارات (في مجلد tests؟ كم ملف؟ في CI؟).
from pathlib import PurePosixPath

from repolens.core.readers import CODE_EXTENSIONS, is_test_file
from repolens.evaluators.base import BaseEvaluator, tag
from repolens.models import RepoSnapshot

CI_MARKERS = (".github/workflows/", ".gitlab-ci.yml", ".circleci/", "azure-pipelines.yml", "Jenkinsfile")
TEST_CONFIG_FILES = {"pytest.ini", "tox.ini", "conftest.py", "jest.config.js", "jest.config.ts", "vitest.config.ts"}


class TestsEvaluator(BaseEvaluator):
    __test__ = False  # بيمنع pytest يفكر إنه هاد class اختبارات بسبب اسمه

    area = "tests"
    focus = (
        "Judge testing and automation. Check: do tests exist at all; how many test files compared to "
        "source files; is there a test configuration; is there CI (for example GitHub Actions) that "
        "runs the tests automatically. No tests at all should score 0-2. A few tests with no CI is "
        "around 4-6. Good coverage of the main modules plus CI is 8-10."
    )

    def build_prompt(self, snapshot: RepoSnapshot) -> str:
        paths = [PurePosixPath(p) for p in snapshot.file_tree]
        test_files = [p.as_posix() for p in paths if is_test_file(p) and p.suffix in CODE_EXTENSIONS]
        source_files = [p.as_posix() for p in paths if p.suffix in CODE_EXTENSIONS and not is_test_file(p)]
        ci_files = [p for p in snapshot.file_tree if any(m in p for m in CI_MARKERS)]
        config_files = [p.as_posix() for p in paths if p.name in TEST_CONFIG_FILES]

        facts = "\n".join([
            f"has a tests/ directory: {snapshot.has_tests_dir}",
            f"source code files: {len(source_files)}",
            f"test files: {len(test_files)}",
            f"test config files: {', '.join(config_files) or 'none'}",
            f"CI files: {', '.join(ci_files) or 'none'}",
        ])
        listing = "\n".join(test_files[:100]) or "(no test files found)"
        sources = "\n".join(source_files[:100]) or "(no source files found)"

        return (
            f"Repository: {snapshot.url}\n\n"
            + tag(
                "repo_data",
                tag("facts", facts) + "\n" + tag("test_files", listing) + "\n" + tag("source_files", sources),
            )
        )
