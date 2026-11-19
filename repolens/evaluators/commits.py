# CommitsEvaluator: بيقيّم آخر 20 رسالة commit (واضحة؟ ولا "fix" و "update"؟).
from repolens.evaluators.base import BaseEvaluator, tag
from repolens.models import RepoSnapshot


class CommitsEvaluator(BaseEvaluator):
    area = "commits"
    focus = (
        "Judge the commit history from the most recent commit messages. Check: do messages explain "
        "what changed and why; vague messages like 'fix', 'update', 'wip', 'asdf' or 'final'; one giant "
        "'initial commit' with the whole project; consistent style (for example Conventional Commits "
        "is a plus, not a requirement); signs of steady incremental work. Only a single commit should "
        "score low because it shows no development history."
    )

    def build_prompt(self, snapshot: RepoSnapshot) -> str:
        messages = snapshot.commit_messages
        if messages:
            body = "\n".join(f"{i}. {m}" for i, m in enumerate(messages, start=1))
            note = f"(the {len(messages)} most recent commits, newest first)"
        else:
            body = "(no commits could be read)"
            note = ""
        return f"Repository: {snapshot.url}\n{note}\n\n" + tag("repo_data", tag("commit_messages", body))
