# اختبار الواجهة بدون LLM: منستبدل analyze بنسخة وهمية ومنتأكد إنه التقرير بينعرض.
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import repolens.pipeline  # noqa: E402
from repolens.models import Finding, Report, SectionResult  # noqa: E402

APP = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "app.py")


async def fake_analyze(url, lang=None, evaluators=None):
    return Report(
        repo_url=url,
        lang=lang or "en",
        overall_score=5.4,
        sections=[
            SectionResult(area="readme", score=8, summary="Clear README."),
            SectionResult(
                area="tests",
                score=2,
                summary="No tests.",
                findings=[Finding(issue="No test suite", evidence="file tree", severity="high")],
                suggestions=["Add pytest tests for the core module"],
            ),
        ],
        improvement_plan=["Add pytest tests for the core module"],
    )


def test_app_renders_report(monkeypatch):
    monkeypatch.setattr(repolens.pipeline, "analyze", fake_analyze)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.radio[0].set_value("en").run()
    at.text_input[0].input("pallets/click")
    at.button[0].click().run()

    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "5.4" in html
    assert "Add pytest tests for the core module" in html
    assert "pallets/click" in html
    assert any("Tests — 2/10" in e.label for e in at.expander)


def test_app_rejects_bad_url():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("gitlab.com/a/b")
    at.button[0].click().run()
    assert at.error and "GitHub" in at.error[0].value
