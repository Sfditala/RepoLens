# RepoLens

[English](../README.md) · **جرّبه:** https://repolens-taupe-nu.vercel.app

> شوف الريبو تبعك متل ما بيشوفه الـ recruiter.

## الفكرة

بتعطي الأداة رابط ريبو على GitHub، فبتقرأه وبترجعلك تقرير بيقيّمه.

ليش مفيدة لجمهور LinkedIn؟ لأن الـ recruiter بيحكم على الريبو من نفس هالأشياء بالضبط، فالأداة بتقلك "هيك شكلك قدام اللي بيوظف".

**المدخل:** رابط ريبو، مثلاً `https://github.com/<user>/TalentIQ`

**شو بتقرأ منه** (أشياء محدودة، مش كل الكود):

- ملف الـ README
- شجرة الملفات (أسماء المجلدات والملفات)
- إذا في مجلد `tests/`، وملف `requirements.txt`، وملف `.gitignore`
- آخر 20 رسالة commit
- عينة صغيرة من ملفات الكود الرئيسية

**المخرج:** تقرير منظم

```
الدرجة: 6/10
- README: ناقص قسم التشغيل، ما فيه صور (الدليل: README.md)
- البنية: كل الكود بملف واحد main.py (الدليل: main.py، 800 سطر)
- الاختبارات: ما في أي اختبار
- Commits: رسائل مثل "fix" و"update" ما بتوضح شي
خطة التحسين: 1) ... 2) ... 3) ...
```

ما فيها RAG ولا سؤال وجواب، وهاد بيخفف الكلفة والتعقيد كتير. السؤال والجواب عن الريبو ممكن ينضاف بعدين كإضافة اختيارية.

---

## كيف بيمشي الشغل

```
رابط الريبو
   │
   ▼
__main__.py            بياخد الرابط من الطرفية
   │
   ▼
pipeline.py            المنسّق
   │
   ├─► core/repo_loader.py    (context manager) بينزّل الريبو بمجلد مؤقت
   │         │
   │         ▼
   │   core/readers.py        (generators) بيقرأ الملفات واحد واحد ← RepoSnapshot
   │         │
   │         ▼
   │   المجلد المؤقت بينحذف تلقائياً
   │
   ├─► asyncio.gather — كل التقييمات بنفس الوقت:
   │       ├── evaluators/readme.py
   │       ├── evaluators/structure.py
   │       ├── evaluators/tests.py
   │       └── evaluators/commits.py
   │       (كلهم بيرثوا من evaluators/base.py، وكل واحد بيستدعي llm.py
   │        وملفوف بـ @retry و @timed من core/decorators.py)
   │
   ├─► كل تقييم بيرجع SectionResult (Pydantic)
   │
   ▼
حساب الدرجة الكلية + خطة التحسين ← Report
   │
   ▼
report.py              بيطبع التقرير بالعربي أو بالإنجليزي
```

---

## هيكلة الملفات

```
RepoLens/
├── repolens/
│   ├── __main__.py          التشغيل من الطرفية
│   ├── config.py            الإعدادات من .env
│   ├── models.py            نماذج Pydantic (RepoSnapshot, SectionResult, Report)
│   ├── llm.py               LangChain + Claude مع structured output
│   ├── pipeline.py          بيربط كل الخطوات ببعض
│   ├── report.py            بيحوّل التقرير لنص
│   ├── core/
│   │   ├── repo_loader.py   context manager للتنزيل المؤقت
│   │   ├── readers.py       generators لقراءة الملفات
│   │   └── decorators.py    retry و timed
│   └── evaluators/
│       ├── base.py          BaseEvaluator (الـ class الأساسي)
│       ├── readme.py
│       ├── structure.py
│       ├── tests.py
│       └── commits.py
├── tests/                   اختبارات pytest
├── requirements.txt
├── .env.example
├── .gitignore
└── pytest.ini
```

---

## وين كل مفهوم من بايثون

| المفهوم | وين | شو بيعمل |
|---|---|---|
| LangChain + Pydantic | `llm.py`, `models.py` | بياخد المعلومات وبيطلّع التقرير بشكل منظم |
| Generators | `core/readers.py` | بتقرأ الملفات واحد واحد |
| async | `pipeline.py` | بتشغّل تقييم الـ README والبنية والاختبارات والـ commits بنفس الوقت |
| Decorators | `core/decorators.py` | بتعيد المحاولة إذا فشل الاستدعاء، وبتحسب الوقت |
| Context manager | `core/repo_loader.py` | بينزّل الريبو مؤقتاً وبينضّفه بعد ما يخلص |
| OOP | `evaluators/` | كل نوع تقييم هو class بيرث من class أساسي |

---

## التشغيل

```bash
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env      # وحط GOOGLE_API_KEY (Gemini) أو ANTHROPIC_API_KEY (Claude) جوّاه
```

**الموقع:**

```bash
uvicorn api.index:app --reload
```

وافتح http://localhost:8000. وعلى Vercel: اعمل import للريبو وحط GOOGLE_API_KEY و REPOLENS_REQUESTS_PER_MINUTE=5 بالـ Environment Variables.

**الطرفية:**

```bash
python -m repolens https://github.com/<user>/<repo>
python -m repolens <user>/<repo> --lang en --json
```

**الاختبارات:**

```bash
pytest                              # بدون API key (LLM وهمي)
python -m scripts.accuracy_check    # دقة حقيقية: المعايرة، الأدلة، الثبات
```

## إضافات لاحقة

- [ ] سؤال وجواب عن الريبو (اختياري)
- [x] واجهة ويب (FastAPI + HTML، بتنرفع على Vercel)
- [ ] صورة للتقرير بتنفع تنحط على LinkedIn
