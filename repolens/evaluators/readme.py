# ReadmeEvaluator: بيقيّم ملف الـ README (وصف، طريقة التشغيل، أمثلة، صور، ...).
from repolens.evaluators.base import BaseEvaluator, clip, tag
from repolens.models import RepoSnapshot


class ReadmeEvaluator(BaseEvaluator):
    area = "readme"
    focus = (
        "Judge the README as the first thing a recruiter reads. Check: a clear one-line description "
        "of what the project does and why it matters; installation and run instructions that actually "
        "work; usage examples; screenshots, a GIF or a demo link; the tech stack; how to run tests; "
        "and clean formatting (headings, code blocks). Compare the instructions against the file tree: "
        "commands that reference files that do not exist are a problem."
    )

    def build_prompt(self, snapshot: RepoSnapshot) -> str:
        if snapshot.readme and snapshot.readme.strip():
            readme = clip(snapshot.readme, 20_000)
        else:
            readme = "(The repository has NO README file.)"
        tree = "\n".join(snapshot.file_tree[:150])
        return (
            f"Repository: {snapshot.url}\n\n"
            + tag("repo_data", tag("readme", readme) + "\n" + tag("file_tree", tree))
        )
