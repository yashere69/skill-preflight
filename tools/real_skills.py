"""Run skill-preflight over a folder of real skills and summarise what it reports.

Used for results/real-skills.md, on two public repositories (commits in that file):

    git clone https://github.com/anthropics/skills /tmp/anthropics-skills
    git clone https://github.com/snyk-labs/toxicskills-goof /tmp/toxicskills-goof
    python tools/real_skills.py /tmp/anthropics-skills/skills
    python tools/real_skills.py /tmp/toxicskills-goof

Only errors and warnings are listed, without spec.* findings, which are about form.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skill_preflight.cli import check_skill  # noqa: E402
from skill_preflight.model import find_skills  # noqa: E402


def main() -> None:
    root = Path(sys.argv[1])
    t0 = time.perf_counter()
    paths = find_skills(root)
    results = [(path, check_skill(path)[0]) for path in paths]
    took = time.perf_counter() - t0
    levels: Counter[str] = Counter()
    print(f"{len(paths)} skills under {root} in {took:.2f} s\n")
    print("| Skill | Errors and warnings (spec.* left out) |")
    print("|---|---|")
    for path, findings in results:
        levels.update(f.level for f in findings)
        shown = sorted(
            {
                f"{f.rule} ({f.level})"
                for f in findings
                if f.level in ("error", "warning") and not f.rule.startswith("spec.")
            }
        )
        print(f"| {path.name} | {', '.join(shown) or '-'} |")
    print(f"\nAll findings by level: {dict(levels)}")


if __name__ == "__main__":
    main()
