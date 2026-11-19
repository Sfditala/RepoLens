# اختبار الـ API تبع الموقع بدون LLM: منستبدل analyze بنسخة وهمية.
from fastapi.testclient import TestClient

import api.index as web
from repolens import pipeline
from repolens.core.repo_loader import RepoCloneError
from repolens.models import Finding, Report, SectionResult

client = TestClient(web.app)


async def fake_analyze(url, lang=None, evaluators=None):
    return Report(
        repo_url=url,
        lang=lang,
        overall_score=5.4,
        sections=[
            SectionResult(area="readme", score=8, summary="Clear README."),
            SectionResult(
                area="tests",
                score=2,
                findings=[Finding(issue="No test suite", evidence="file tree", severity="high")],
                suggestions=["Add pytest tests"],
            ),
        ],
        improvement_plan=["Add pytest tests"],
    )


def test_analyze_returns_report_and_markdown(monkeypatch):
    web._cache.clear()
    monkeypatch.setattr(pipeline, "analyze", fake_analyze)
    res = client.post("/api/analyze", json={"url": "pallets/click", "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["report"]["repo_url"] == "https://github.com/pallets/click"
    assert body["report"]["overall_score"] == 5.4
    assert "## Tests — 2/10" in body["markdown"]
    assert body["cached"] is False
    # نفس الطلب مرة تانية بييجي من الكاش
    assert client.post("/api/analyze", json={"url": "pallets/click", "lang": "en"}).json()["cached"] is True


def test_invalid_url_is_400():
    res = client.post("/api/analyze", json={"url": "gitlab.com/a/b"})
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_url"


def test_missing_repo_is_404(monkeypatch):
    web._cache.clear()

    async def missing(url, lang=None, evaluators=None):
        raise RepoCloneError("not found")

    monkeypatch.setattr(pipeline, "analyze", missing)
    res = client.post("/api/analyze", json={"url": "someone/nothing-here"})
    assert res.status_code == 404
    assert res.json()["error"] == "repo_unavailable"


def test_model_failure_is_502(monkeypatch):
    web._cache.clear()

    async def boom(url, lang=None, evaluators=None):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(pipeline, "analyze", boom)
    res = client.post("/api/analyze", json={"url": "a/b"})
    assert res.status_code == 502
    assert res.json()["error"] == "analysis_failed"


def test_index_page_and_health():
    assert "RepoLens" in client.get("/").text
    assert client.get("/api/health").json()["status"] == "ok"
