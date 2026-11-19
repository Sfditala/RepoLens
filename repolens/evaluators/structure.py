# StructureEvaluator: بيقيّم تنظيم المشروع من شجرة الملفات وعينات الكود (ملف ضخم واحد؟ تقسيم لموديولات؟ requirements و .gitignore؟).
from repolens.evaluators.base import BaseEvaluator, tag
from repolens.models import RepoSnapshot

MAX_TREE_ENTRIES = 400


class StructureEvaluator(BaseEvaluator):
    area = "structure"
    focus = (
        "Judge how the project is organized and how clean the code looks. Check: is the code split "
        "into sensible modules or crammed into one huge file; clear folder and file names; a "
        "dependency file (requirements.txt, pyproject.toml, package.json ...); a .gitignore; no "
        "committed junk (virtualenvs, __pycache__, .env files with secrets, large data or model "
        "files, .DS_Store); and, from the code samples, readable naming, functions of reasonable "
        "size, and no obvious hard-coded secrets."
    )

    def build_prompt(self, snapshot: RepoSnapshot) -> str:
        tree_lines = snapshot.file_tree[:MAX_TREE_ENTRIES]
        tree = "\n".join(tree_lines)
        if len(snapshot.file_tree) > MAX_TREE_ENTRIES:
            tree += f"\n[... {len(snapshot.file_tree) - MAX_TREE_ENTRIES} more files not shown]"

        facts = "\n".join([
            f"total files: {len(snapshot.file_tree)}",
            f"has dependency file: {snapshot.has_requirements}",
            f"has .gitignore: {snapshot.has_gitignore}",
        ])

        samples = "\n\n".join(
            tag(
                "code_sample",
                f"path: {s.path}\ntotal lines: {s.lines}\n"
                f"(first {len(s.content.splitlines())} lines shown)\n---\n{s.content}",
            )
            for s in snapshot.code_samples
        ) or "(no source code files found)"

        return (
            f"Repository: {snapshot.url}\n\n"
            + tag("repo_data", tag("facts", facts) + "\n" + tag("file_tree", tree) + "\n" + samples)
        )
