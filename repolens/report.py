# بيحوّل الـ Report لنص مقروء (عربي أو إنجليزي) بالشكل اللي بينطبع للمستخدم.
from repolens.models import Report

LABELS = {
    "ar": {
        "title": "تقرير RepoLens",
        "score": "الدرجة",
        "plan": "خطة التحسين",
        "evidence": "الدليل",
        "suggestions": "اقتراحات",
        "no_findings": "ما في مشاكل واضحة",
        "failed": "ما قدرنا نقيّم",
        "areas": {"readme": "README", "structure": "البنية", "tests": "الاختبارات", "commits": "Commits"},
        "severity": {"high": "عالية", "medium": "متوسطة", "low": "منخفضة"},
    },
    "en": {
        "title": "RepoLens report",
        "score": "Score",
        "plan": "Improvement plan",
        "evidence": "evidence",
        "suggestions": "Suggestions",
        "no_findings": "No clear problems",
        "failed": "Could not evaluate",
        "areas": {"readme": "README", "structure": "Structure", "tests": "Tests", "commits": "Commits"},
        "severity": {"high": "high", "medium": "medium", "low": "low"},
    },
}


def labels(lang: str) -> dict:
    return LABELS.get(lang, LABELS["en"])


def area_title(area: str, lang: str) -> str:
    return labels(lang)["areas"].get(area, area)


def render_text(report: Report) -> str:
    t = labels(report.lang)
    lines = [
        f"{t['title']}: {report.repo_url}",
        f"{t['score']}: {report.overall_score:g}/10",
        "",
    ]
    if report.failed_areas:
        failed = ", ".join(area_title(a, report.lang) for a in report.failed_areas)
        lines += [f"⚠ {t['failed']}: {failed}", ""]
    for section in report.sections:
        lines.append(f"■ {area_title(section.area, report.lang)}: {section.score}/10")
        if section.summary:
            lines.append(f"  {section.summary}")
        if not section.findings:
            lines.append(f"  - {t['no_findings']}")
        for f in section.findings:
            lines.append(f"  - [{t['severity'][f.severity]}] {f.issue} ({t['evidence']}: {f.evidence})")
        lines.append("")
    lines.append(f"{t['plan']}:")
    for i, step in enumerate(report.improvement_plan, start=1):
        lines.append(f"  {i}) {step}")
    return "\n".join(lines)


def render_markdown(report: Report) -> str:
    t = labels(report.lang)
    out = [
        f"# {t['title']}",
        "",
        f"**Repo:** {report.repo_url}  ",
        f"**{t['score']}:** {report.overall_score:g}/10",
        "",
    ]
    if report.failed_areas:
        out += [f"> ⚠ {t['failed']}: " + ", ".join(area_title(a, report.lang) for a in report.failed_areas), ""]
    out += [
        "| | |",
        "|---|---|",
    ]
    out += [f"| {area_title(s.area, report.lang)} | {s.score}/10 |" for s in report.sections]
    for s in report.sections:
        out += ["", f"## {area_title(s.area, report.lang)} — {s.score}/10", ""]
        if s.summary:
            out += [s.summary, ""]
        for f in s.findings:
            out.append(f"- **{t['severity'][f.severity]}** · {f.issue} — _{t['evidence']}: {f.evidence}_")
        if s.suggestions:
            out += ["", f"**{t['suggestions']}:**"]
            out += [f"- {x}" for x in s.suggestions]
    out += ["", f"## {t['plan']}", ""]
    out += [f"{i}. {step}" for i, step in enumerate(report.improvement_plan, start=1)]
    return "\n".join(out) + "\n"
