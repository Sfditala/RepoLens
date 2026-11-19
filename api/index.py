# الـ API تبع الموقع (FastAPI). على Vercel كل طلب لـ /api/* بيوصل هون كـ serverless function،
# والصفحة نفسها (public/index.html) بتنخدم كملف static.
# محلياً:  uvicorn api.index:app --reload   وافتح http://localhost:8000
import logging
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from repolens import pipeline
from repolens.config import settings
from repolens.core.repo_loader import RepoCloneError
from repolens.llm import MissingApiKeyError
from repolens.models import Report
from repolens.report import render_markdown

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("repolens.api")

PUBLIC = Path(__file__).resolve().parent.parent / "public"
CACHE_TTL_SECONDS = 3600
_cache: dict[tuple[str, str], tuple[float, dict]] = {}

app = FastAPI(title="RepoLens", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


class AnalyzeRequest(BaseModel):
    url: str
    lang: Literal["ar", "en"] = "en"


class AnalyzeResponse(BaseModel):
    report: Report
    markdown: str
    cached: bool = False


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "provider": settings.resolved_provider(),
        "model": settings.resolved_model(),
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    try:
        url = pipeline.normalize_url(req.url)
    except pipeline.InvalidRepoUrlError as exc:
        return error(400, "invalid_url", str(exc))

    # كاش بسيط بالذاكرة: نفس الريبو بنفس اللغة خلال ساعة ما بيصرف من حصة الـ API مرة تانية
    key = (url, req.lang)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_SECONDS:
        return {**hit[1], "cached": True}

    try:
        report = await pipeline.analyze(url, lang=req.lang)
    except RepoCloneError as exc:
        return error(404, "repo_unavailable", str(exc))
    except MissingApiKeyError:
        logger.error("No model API key configured")
        return error(503, "not_configured", "The server has no model API key configured.")
    except Exception as exc:  # noqa: BLE001 - مثلاً حصة الموديل خلصت أو الموديل مضغوط
        logger.exception("Analysis failed for %s", url)
        return error(502, "analysis_failed", f"The model could not finish the review: {type(exc).__name__}")

    payload = {"report": report.model_dump(), "markdown": render_markdown(report)}
    _cache[key] = (time.time(), payload)
    return {**payload, "cached": False}


# محلياً بس: نخدم الصفحة من نفس السيرفر. على Vercel الصفحة static وما بتوصل لهون.
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(PUBLIC / "index.html")
