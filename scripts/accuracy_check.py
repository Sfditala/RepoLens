"""Accuracy check for RepoLens against real repositories (uses the real API, costs a few cents).

Three checks:
1. Calibration  - a weak repo and a strong repo must land in the expected score bands.
2. Grounding    - every file a finding cites as evidence must really exist in the repo
                  (catches hallucinated evidence).
3. Stability    - analyzing the same repo twice should give close scores.

Run:  python -m scripts.accuracy_check
"""

import asyncio
import re
import sys

from repolens.models import Report, RepoSnapshot
from repolens.pipeline import collect_snapshot, evaluate_snapshot

CASES = [
    # (repo, overall band, per-area bands)
    ("https://github.com/octocat/Hello-World", (0, 4), {"tests": (0, 2), "structure": (0, 4)}),
    ("https://github.com/pallets/itsdangerous", (7, 10), {"tests": (7, 10), "structure": (7, 10)}),
]
STABILITY_REPO = "https://github.com/pallets/itsdangerous"
STABILITY_TOLERANCE = 1.0

FILE_TOKEN = re.compile(r"[\w./-]+\.[A-Za-z0-9]{1,6}\b|[\w-]+/[\w./-]+")


def cited_files(evidence: str) -> list[str]:
    tokens = []
    for raw in FILE_TOKEN.findall(evidence):
        token = raw.strip("./`'\"")
        if token and not token.startswith(("http", "github.com")) and not re.fullmatch(r"[\d.]+", token):
            tokens.append(token)
    return tokens


def grounding(report: Report, snap: RepoSnapshot) -> tuple[int, int, list[str]]:
    tree = set(snap.file_tree)
    names = {p.rsplit("/", 1)[-1] for p in tree}
    dirs = {p.rsplit("/", 1)[0] for p in tree if "/" in p}
    checked = ok = 0
    missing = []
    for s in report.sections:
        for f in s.findings:
            for token in cited_files(f.evidence):
                checked += 1
                if token in tree or token in names or token.rstrip("/") in dirs or any(
                    p.endswith(token) for p in tree
                ):
                    ok += 1
                else:
                    missing.append(f"[{s.area}] {token}  <- {f.evidence}")
    return checked, ok, missing


def in_band(value: float, band: tuple[float, float]) -> bool:
    return band[0] <= value <= band[1]


async def run_case(url: str, lang: str = "en") -> tuple[Report, RepoSnapshot]:
    snap = await asyncio.to_thread(collect_snapshot, url)
    return await evaluate_snapshot(snap, lang=lang), snap


async def main() -> int:
    failures = 0
    total_checked = total_ok = 0

    print("== Calibration + grounding ==")
    for url, band, area_bands in CASES:
        report, snap = await run_case(url)
        scores = {s.area: s.score for s in report.sections}
        good = in_band(report.overall_score, band)
        print(f"\n{url}\n  overall {report.overall_score} expected {band} -> {'PASS' if good else 'FAIL'}")
        failures += not good
        for area, area_band in area_bands.items():
            ok = in_band(scores[area], area_band)
            failures += not ok
            print(f"  {area:<9} {scores[area]:>2} expected {area_band} -> {'PASS' if ok else 'FAIL'}")
        print(f"  all areas: {scores}")
        checked, ok, missing = grounding(report, snap)
        total_checked += checked
        total_ok += ok
        print(f"  evidence grounded: {ok}/{checked}")
        for m in missing:
            print(f"    ? {m}")

    rate = total_ok / total_checked if total_checked else 1.0
    print(f"\nGrounding rate: {rate:.0%} ({total_ok}/{total_checked})")
    if rate < 0.9:
        failures += 1

    print("\n== Stability ==")
    (r1, _), (r2, _) = await asyncio.gather(run_case(STABILITY_REPO), run_case(STABILITY_REPO))
    diff = abs(r1.overall_score - r2.overall_score)
    stable = diff <= STABILITY_TOLERANCE
    failures += not stable
    print(f"{STABILITY_REPO}: {r1.overall_score} vs {r2.overall_score} (diff {diff:.1f}) -> {'PASS' if stable else 'FAIL'}")

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
