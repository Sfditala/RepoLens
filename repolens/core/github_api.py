# بديل لـ git clone: بينزّل الريبو عن طريق GitHub API (ملف tarball) وبيجيب رسائل الـ commits.
# ليش؟ على Vercel ما في git، بس في إنترنت. وكمان أسرع لأنه ما بينزّل تاريخ .git.
#
# 📝 نوتات:
# - downloaded_repo هو كمان context manager (متل cloned_repo): بينزّل لمجلد مؤقت وبيمسحه بالآخر.
# - منقرأ الـ tarball "stream" ومنوقف إذا كبر عن الحد، عشان ريبو ضخم ما يعبّي الذاكرة.
# - tarfile filter="data": بيمنع ملف بالأرشيف يكتب برا المجلد (حماية من path traversal).
# - GITHUB_TOKEN اختياري: بدونه GitHub بيسمح 60 طلب بالساعة لكل IP (وكل تحليل = 2 طلبات).
import io
import os
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx

from repolens.core.repo_loader import RepoCloneError

API = "https://api.github.com"
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024  # 60 MB


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoLens"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def split_url(url: str) -> tuple[str, str]:
    owner, repo = url.rstrip("/").split("/")[-2:]
    return owner, repo


def _raise_for_status(response: httpx.Response, url: str) -> None:
    if response.status_code == 404:
        raise RepoCloneError(f"Repository {url} was not found or is private.")
    if response.status_code in (403, 429):
        raise RepoCloneError("GitHub API rate limit reached. Try again later or set GITHUB_TOKEN.")
    if response.status_code >= 400:
        raise RepoCloneError(f"GitHub API error {response.status_code} for {url}.")


def _download_tarball(url: str) -> bytes:
    owner, repo = split_url(url)
    buffer = io.BytesIO()
    with httpx.Client(headers=_headers(), follow_redirects=True, timeout=60) as client:
        with client.stream("GET", f"{API}/repos/{owner}/{repo}/tarball") as response:
            _raise_for_status(response, url)
            for chunk in response.iter_bytes():
                buffer.write(chunk)
                if buffer.tell() > MAX_DOWNLOAD_BYTES:
                    raise RepoCloneError(f"{url} is too large to analyze (over 60 MB).")
    return buffer.getvalue()


@contextmanager
def downloaded_repo(url: str) -> Iterator[Path]:
    data = _download_tarball(url)
    with tempfile.TemporaryDirectory(prefix="repolens_") as tmp:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            archive.extractall(tmp, filter="data")
        # الأرشيف فيه مجلد واحد اسمه owner-repo-<sha>
        folders = [p for p in Path(tmp).iterdir() if p.is_dir()]
        if len(folders) != 1:
            raise RepoCloneError(f"Unexpected archive layout for {url}.")
        yield folders[0]


def fetch_commit_messages(url: str, limit: int) -> list[str]:
    owner, repo = split_url(url)
    with httpx.Client(headers=_headers(), timeout=30) as client:
        response = client.get(f"{API}/repos/{owner}/{repo}/commits", params={"per_page": limit})
    if response.status_code == 409:  # ريبو فاضي
        return []
    _raise_for_status(response, url)
    messages = []
    for item in response.json():
        first_line = item["commit"]["message"].strip().splitlines()[0] if item["commit"]["message"].strip() else ""
        if first_line:
            messages.append(first_line)
    return messages
