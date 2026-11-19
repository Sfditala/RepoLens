# واجهة RepoLens (Streamlit): بتاخد رابط الريبو، بتشغّل نفس الـ pipeline تبع الطرفية، وبتعرض التقرير.
# التشغيل:  streamlit run app.py
import asyncio
import json

import streamlit as st

from repolens.core.repo_loader import RepoCloneError
from repolens.llm import MissingApiKeyError
from repolens.models import Report
from repolens.pipeline import InvalidRepoUrlError, analyze, normalize_url
from repolens.report import area_title, labels, render_markdown

UI = {
    "ar": {
        "tagline": "شوف الريبو تبعك متل ما بيشوفه الـ recruiter.",
        "input": "رابط الريبو على GitHub",
        "placeholder": "https://github.com/user/repo",
        "button": "حلّل الريبو",
        "running": "عم ننزّل الريبو ونقيّمه… (بياخد دقيقة لـ 3 دقايق)",
        "overall": "الدرجة الكلية",
        "verdict": ["بدها شغل كتير", "مقبولة", "منيحة", "ممتازة"],
        "summary": "الخلاصة",
        "findings": "المشاكل",
        "suggestions": "الاقتراحات",
        "download_md": "نزّل التقرير (Markdown)",
        "download_json": "نزّل التقرير (JSON)",
        "what": "شو بنفحص؟",
        "what_body": "README · بنية المشروع وجودة الكود · الاختبارات و CI · رسائل الـ commits. "
        "منقرأ أشياء محدودة بس (مش كل الكود)، وكل ملاحظة إلها دليل من الريبو.",
        "errors": {
            "url": "الرابط مش رابط ريبو GitHub. جرّب: https://github.com/user/repo",
            "clone": "ما قدرنا ننزّل الريبو. تأكد إنه موجود وعام (public).",
            "key": "ما في API key. حط GOOGLE_API_KEY (أو ANTHROPIC_API_KEY) بملف .env وأعد تشغيل التطبيق.",
            "other": "صار خطأ غير متوقع:",
        },
    },
    "en": {
        "tagline": "See your repo the way a recruiter sees it.",
        "input": "GitHub repository URL",
        "placeholder": "https://github.com/user/repo",
        "button": "Analyze repo",
        "running": "Cloning and reviewing the repo… (takes 1–3 minutes)",
        "overall": "Overall score",
        "verdict": ["Needs a lot of work", "Fair", "Good", "Excellent"],
        "summary": "Summary",
        "findings": "Findings",
        "suggestions": "Suggestions",
        "download_md": "Download report (Markdown)",
        "download_json": "Download report (JSON)",
        "what": "What does it check?",
        "what_body": "README · project structure and code quality · tests and CI · commit messages. "
        "It reads a limited sample (not the whole codebase), and every finding cites evidence from the repo.",
        "errors": {
            "url": "That is not a GitHub repository URL. Try: https://github.com/user/repo",
            "clone": "Could not clone the repo. Make sure it exists and is public.",
            "key": "No API key found. Put GOOGLE_API_KEY (or ANTHROPIC_API_KEY) in .env and restart the app.",
            "other": "Unexpected error:",
        },
    },
}

SEVERITY_COLOR = {"high": "#d1453b", "medium": "#d98a1c", "low": "#6b7a8c"}


def score_color(score: float) -> str:
    if score >= 8:
        return "#1f9d55"
    if score >= 6:
        return "#3d7dd8"
    if score >= 4:
        return "#d98a1c"
    return "#d1453b"


def verdict(score: float, t: dict) -> str:
    return t["verdict"][0 if score < 4 else 1 if score < 6 else 2 if score < 8 else 3]


@st.cache_data(show_spinner=False, ttl=3600)
def run_analysis(url: str, lang: str) -> dict:
    # الكاش: نفس الريبو بنفس اللغة خلال ساعة ما بيرجع يدفع على الـ API
    return asyncio.run(analyze(url, lang=lang)).model_dump()


def inject_css(lang: str) -> None:
    direction = "rtl" if lang == "ar" else "ltr"
    st.markdown(
        f"""
        <style>
        .block-container {{ max-width: 980px; padding-top: 2.2rem; }}
        .rl-dir {{ direction: {direction}; text-align: {"right" if lang == "ar" else "left"}; }}
        .rl-hero h1 {{ font-size: 2.4rem; margin-bottom: 0; }}
        .rl-hero p {{ opacity: .75; font-size: 1.1rem; margin-top: .2rem; }}
        .rl-score {{ border-radius: 18px; padding: 22px 26px; color: #fff; }}
        .rl-score .num {{ font-size: 3.4rem; font-weight: 800; line-height: 1; }}
        .rl-score .lbl {{ opacity: .9; font-size: 1rem; }}
        .rl-card {{ border: 1px solid rgba(128,128,128,.25); border-radius: 14px; padding: 14px 16px; height: 100%; }}
        .rl-card .t {{ font-size: .95rem; opacity: .75; }}
        .rl-card .s {{ font-size: 1.8rem; font-weight: 700; }}
        .rl-bar {{ height: 6px; border-radius: 3px; background: rgba(128,128,128,.2); margin-top: 6px; }}
        .rl-bar > div {{ height: 6px; border-radius: 3px; }}
        .rl-sev {{ display: inline-block; color: #fff; border-radius: 6px; padding: 0 8px; font-size: .8rem; margin-inline-end: 6px; }}
        .rl-evidence {{ opacity: .7; font-size: .88rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_report(report: Report, t: dict) -> None:
    lang = report.lang
    lab = labels(lang)
    color = score_color(report.overall_score)

    st.markdown(
        f"""<div class="rl-score rl-dir" style="background:{color}">
        <div class="lbl">{t["overall"]} · <a href="{report.repo_url}" style="color:#fff">{html_escape(report.repo_url.removeprefix("https://github.com/"))}</a></div>
        <div class="num">{report.overall_score:g}<span style="font-size:1.6rem;opacity:.8">/10</span></div>
        <div class="lbl">{verdict(report.overall_score, t)}</div></div>""",
        unsafe_allow_html=True,
    )
    if report.failed_areas:
        failed = ", ".join(area_title(a, lang) for a in report.failed_areas)
        st.warning(f"{lab['failed']}: {failed}")
    st.write("")

    cols = st.columns(len(report.sections))
    for col, s in zip(cols, report.sections):
        c = score_color(s.score)
        col.markdown(
            f"""<div class="rl-card rl-dir"><div class="t">{area_title(s.area, lang)}</div>
            <div class="s" style="color:{c}">{s.score}/10</div>
            <div class="rl-bar"><div style="width:{s.score * 10}%;background:{c}"></div></div></div>""",
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown(f"<div class='rl-dir'><h3>{lab['plan']}</h3></div>", unsafe_allow_html=True)
    plan = "".join(f"<li>{html_escape(step)}</li>" for step in report.improvement_plan)
    st.markdown(f"<div class='rl-dir'><ol>{plan}</ol></div>", unsafe_allow_html=True)

    for s in sorted(report.sections, key=lambda x: x.score):
        with st.expander(f"{area_title(s.area, lang)} — {s.score}/10", expanded=s.score < 6):
            body = [f"<p><b>{t['summary']}:</b> {html_escape(s.summary)}</p>"] if s.summary else []
            if s.findings:
                body.append(f"<p><b>{t['findings']}:</b></p><ul>")
                for f in s.findings:
                    body.append(
                        f"<li><span class='rl-sev' style='background:{SEVERITY_COLOR[f.severity]}'>"
                        f"{lab['severity'][f.severity]}</span>{html_escape(f.issue)}"
                        f"<div class='rl-evidence'>{lab['evidence']}: <code>{html_escape(f.evidence)}</code></div></li>"
                    )
                body.append("</ul>")
            else:
                body.append(f"<p>{lab['no_findings']}</p>")
            if s.suggestions:
                body.append(f"<p><b>{t['suggestions']}:</b></p><ul>")
                body += [f"<li>{html_escape(x)}</li>" for x in s.suggestions]
                body.append("</ul>")
            st.markdown(f"<div class='rl-dir'>{''.join(body)}</div>", unsafe_allow_html=True)

    st.write("")
    name = report.repo_url.rstrip("/").split("/")[-1]
    d1, d2 = st.columns(2)
    d1.download_button(t["download_md"], render_markdown(report), file_name=f"repolens-{name}.md", mime="text/markdown")
    d2.download_button(
        t["download_json"],
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
        file_name=f"repolens-{name}.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="RepoLens", page_icon="🔍", layout="centered")

    lang = st.radio("Language / اللغة", ["ar", "en"], format_func=lambda x: "العربية" if x == "ar" else "English", horizontal=True)
    t = UI[lang]
    inject_css(lang)

    st.markdown(f"<div class='rl-hero rl-dir'><h1>🔍 RepoLens</h1><p>{t['tagline']}</p></div>", unsafe_allow_html=True)

    with st.form("analyze"):
        url = st.text_input(t["input"], placeholder=t["placeholder"])
        submitted = st.form_submit_button(t["button"], type="primary", use_container_width=True)

    with st.expander(t["what"]):
        st.markdown(f"<div class='rl-dir'>{t['what_body']}</div>", unsafe_allow_html=True)

    if not submitted:
        return

    try:
        canonical = normalize_url(url)
        with st.spinner(t["running"]):
            report = Report.model_validate(run_analysis(canonical, lang))
    except InvalidRepoUrlError:
        st.error(t["errors"]["url"])
        return
    except RepoCloneError:
        st.error(t["errors"]["clone"])
        return
    except MissingApiKeyError:
        st.error(t["errors"]["key"])
        return
    except Exception as exc:  # noqa: BLE001 - نعرض أي خطأ تاني للمستخدم بدل ما تنهار الصفحة
        st.error(f"{t['errors']['other']} {exc}")
        return

    show_report(report, t)


main()
