# 🔍 RepoLens

**See your GitHub repo the way a recruiter sees it.**

Paste a public GitHub repository URL and RepoLens returns a scored, evidence-backed review of the four things a hiring manager looks at in the first two minutes: the README, the project structure, the tests, and the commit history. It finishes with a short, prioritized improvement plan.

[العربية](docs/README.ar.md)

<!-- Add a screenshot of the UI here: docs/screenshot.png -->

```
Score: 6.2/10
■ README: 7/10      clear description, but no install steps   (evidence: README.md)
■ Structure: 5/10   all logic in one 800-line file            (evidence: main.py, 812 lines)
■ Tests: 2/10       no test suite and no CI                    (evidence: file tree)
■ Commits: 6/10     several vague messages                     (evidence: "fix", "update")
Improvement plan: 1) Add pytest tests for the core module  2) Split main.py into modules  3) ...
```

## Features

- **Four focused reviewers** (README, structure, tests, commits) that run **in parallel**.
- **Every finding cites evidence** — a file name, a line count, or a commit message.
- **Calibrated 0–10 scores** with a weighted overall score.
- **Arabic or English** reports.
- **Web UI** (Streamlit) and **CLI**, with Markdown/JSON export.
- **Gemini or Claude**, switchable from `.env`.
- **Cheap by design:** reads a limited sample (README, file tree, last 20 commits, the 5 largest source files) instead of the whole codebase — no RAG, no embeddings.

## How it works

```
GitHub URL
   │
   ▼
pipeline.py ─► core/repo_loader.py   shallow `git clone` into a temp dir (context manager, always cleaned up)
           ─► core/readers.py        generators walk the files → RepoSnapshot (Pydantic)
           ─► asyncio.gather          4 evaluators run concurrently
                 ├─ evaluators/readme.py
                 ├─ evaluators/structure.py
                 ├─ evaluators/tests.py
                 └─ evaluators/commits.py
                 (all inherit BaseEvaluator · LLM call wrapped in @retry and @timed)
           ─► weighted score + improvement plan → Report
   │
   ▼
report.py (text / Markdown)   ·   app.py (web UI)   ·   __main__.py (CLI)
```

The LLM layer (`llm.py`) uses LangChain with **structured outputs** (`with_structured_output(..., method="json_schema")`), so each reviewer returns a validated Pydantic object instead of free text. It works with **Google Gemini** (`ChatGoogleGenerativeAI`) or **Anthropic Claude** (`ChatAnthropic`); the rest of the code never knows which one is behind it.

| Python concept | Where |
|---|---|
| LangChain + Pydantic structured output (Gemini or Claude) | `llm.py`, `models.py` |
| Generators | `core/readers.py` |
| async / `asyncio.gather` | `pipeline.py` |
| Decorators (`@retry`, `@timed`) | `core/decorators.py` |
| Context manager | `core/repo_loader.py` |
| OOP: abstract base class + inheritance | `evaluators/` |

## Quick start

Requires Python 3.11+ and `git`.

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Put a [Google AI Studio key](https://aistudio.google.com/apikey) in `.env` (`GOOGLE_API_KEY=...`), or an Anthropic key (`ANTHROPIC_API_KEY=...`) to use Claude, then:

**Web UI**

```bash
streamlit run app.py
```

**CLI**

```bash
python -m repolens https://github.com/<user>/<repo>
python -m repolens <user>/<repo> --lang en
python -m repolens <user>/<repo> --json > report.json
```

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `REPOLENS_PROVIDER` | `auto` | `gemini`, `anthropic`, or `auto` (whichever key is set) |
| `GOOGLE_API_KEY` | — | Google AI Studio key (Gemini) |
| `ANTHROPIC_API_KEY` | — | Anthropic key (Claude) |
| `REPOLENS_GEMINI_MODEL` | `gemini-3.5-flash` | Gemini model |
| `REPOLENS_GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` | Used when the main model is overloaded or out of quota |
| `REPOLENS_REQUESTS_PER_MINUTE` | `0` (unlimited) | Set to `5` for the Gemini free tier |
| `REPOLENS_ANTHROPIC_MODEL` | `claude-opus-5-5` | Claude model |
| `REPOLENS_EFFORT` | `medium` | How much the model reasons: `low` … `max` |
| `REPOLENS_REPORT_LANG` | `ar` | `ar` or `en` |
| `REPOLENS_MAX_COMMITS` | `20` | Commits to read |
| `REPOLENS_MAX_CODE_FILES` | `5` | Source files sampled |
| `REPOLENS_MAX_LINES_PER_FILE` | `150` | Lines read per sampled file |
| `REPOLENS_REFUSAL_FALLBACK` | `true` | Claude only: retry a refused request on a fallback model |

## Tests and accuracy

```bash
pytest                              # unit + UI tests, no API key needed (fake LLM)
python -m scripts.accuracy_check    # real API: calibration, evidence grounding, stability
```

`scripts/accuracy_check.py` runs the full pipeline on real repositories and checks that:

- a near-empty repo (`octocat/Hello-World`) scores low and a mature library (`pallets/itsdangerous`) scores high;
- every file a finding cites as evidence actually exists in the repo (no hallucinated evidence);
- analyzing the same repo twice gives scores within 1 point.

Latest run (Gemini `gemini-3.5-flash`, falling back to `gemini-3.5-flash-lite`):

| Check | Result |
|---|---|
| `octocat/Hello-World` (expected 0–4) | **1.7** · README 1, structure 2, tests 0, commits 4 ✅ |
| `pallets/itsdangerous` (expected 7–10) | **8.5** · README 7, structure 10, tests 9, commits 8 ✅ |
| Evidence grounding | 2/2 cited files exist ✅ (small sample) |
| Stability (same repo twice) | 8.0 vs 7.9 ✅ |

> **Gemini free tier:** about 5 requests per minute and 20 per day per model. One analysis uses 4 requests, so set `REPOLENS_REQUESTS_PER_MINUTE=5`. When the main model is out of quota or overloaded (503), RepoLens switches to `REPOLENS_GEMINI_FALLBACK_MODEL` automatically. If one area still fails, you get a partial report that names the missing area.

## Project layout

```
repolens/
├── __main__.py          CLI
├── config.py            settings from .env
├── models.py            Pydantic models (RepoSnapshot, SectionResult, Report)
├── llm.py               LangChain + Gemini/Claude structured output
├── pipeline.py          orchestration, URL validation, scoring, plan
├── report.py            text / Markdown rendering
├── core/                repo_loader, readers, decorators
└── evaluators/          base + readme, structure, tests, commits
app.py                   Streamlit UI
scripts/accuracy_check.py
tests/
```

## Limitations

- Public GitHub repositories only.
- Reviews a sample of the code, not every file, so it judges presentation and structure rather than correctness.
- Scores come from an LLM: treat them as a well-informed second opinion, not ground truth.

## Roadmap

- [ ] Ask questions about the repo (optional Q&A)
- [ ] Shareable report image for LinkedIn
