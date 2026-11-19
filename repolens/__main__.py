# نقطة التشغيل من الطرفية: python -m repolens <رابط الريبو> [--json] [--lang en] [-v]
# بتقرأ الرابط من الـ arguments، بتشغّل الـ pipeline، وبتطبع التقرير.
import argparse
import asyncio
import logging
import sys

from repolens.core.repo_loader import RepoCloneError
from repolens.llm import MissingApiKeyError
from repolens.pipeline import InvalidRepoUrlError, analyze
from repolens.report import render_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repolens",
        description="See your GitHub repo the way a recruiter sees it.",
    )
    parser.add_argument("url", help="https://github.com/<user>/<repo> or <user>/<repo>")
    parser.add_argument("--lang", choices=["ar", "en"], help="report language (default: from .env)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="show timing and retry logs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    # الطرفية على ويندوز ممكن ما تطبع عربي بدون هاد
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        report = asyncio.run(analyze(args.url, lang=args.lang))
    except (InvalidRepoUrlError, RepoCloneError, MissingApiKeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - مثلاً تجاوز حد الطلبات أو مشكلة نت
        print(f"error: analysis failed: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
        return 1

    print(report.model_dump_json(indent=2) if args.json else render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
