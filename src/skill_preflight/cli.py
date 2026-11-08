"""skill-preflight command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, budget, capabilities, conformance, instructions, lock, output
from .model import Finding, find_skills, load

LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}
MARK = {"error": "E", "warning": "W", "info": "i"}


def check_skill(path: Path) -> tuple[list[Finding], budget.Budget]:
    skill = load(path)
    findings = list(conformance.check(skill))
    if skill.frontmatter is not None:
        findings += budget.check(skill)
        findings += capabilities.check(skill)
        findings += instructions.check(skill)
    findings.sort(key=lambda f: (LEVEL_ORDER[f.level], f.rule))
    return findings, budget.measure(skill)


def _bar(n: int, limit: int, width: int = 24) -> str:
    filled = min(width, round(width * n / limit))
    return "#" * filled + "." * (width - filled)


def cmd_check(paths: list[Path], strict: bool, fmt: str = "text") -> int:
    worst = 2
    skills = [s for p in paths for s in find_skills(p)]
    if not skills:
        print("no skills found (looked for SKILL.md)", file=sys.stderr)
        return 2
    results = [(path, *check_skill(path)) for path in skills]
    for _, findings, _ in results:
        for f in findings:
            worst = min(worst, LEVEL_ORDER[f.level])
    exit_code = 1 if worst == 0 or (strict and worst == 1) else 0
    if fmt != "text":
        print(output.to_json(results) if fmt == "json" else output.to_sarif(results))
        return exit_code
    for path, findings, b in results:
        print(f"{path.name}")
        print(
            f"  body    [{_bar(b.body_tokens, 5000)}] ~{b.body_tokens} / 5000 tokens, "
            f"{b.body_lines} lines"
        )
        print(f"  always  ~{b.metadata_tokens} tokens of name+description in every session")
        for f in findings:
            print(f"  [{MARK[f.level]}] {f.rule:<20} {f.message}  ({f.where})")
        if not findings:
            print("  no findings")
        print()
    print("No findings does not mean safe. This tool checks structure and declared behaviour;")
    print("it cannot tell what a script or an instruction is for.")
    return exit_code


def cmd_lock(paths: list[Path], lockfile: Path) -> int:
    skills = [load(s) for p in paths for s in find_skills(p)]
    seen: dict[str, Path] = {}
    for s in skills:
        if s.name in seen:
            print(
                f"error: two skills are named {s.name!r} ({seen[s.name]} and {s.root}); "
                "the lockfile keys skills by name, so one would hide the other",
                file=sys.stderr,
            )
            return 2
        seen[s.name] = s.root
    lock.write(lockfile, skills)
    print(f"locked {len(skills)} skill(s) in {lockfile}")
    return 0


def cmd_diff(paths: list[Path], lockfile: Path) -> int:
    if not lockfile.exists():
        print(
            f"error: no lockfile at {lockfile}. Run `skill-preflight lock "
            f"{' '.join(str(p) for p in paths)}` first, or pass --lockfile.",
            file=sys.stderr,
        )
        return 2
    locked = lock.read(lockfile)
    worst = "none"
    rank = ["high", "medium", "low", "none"]
    found: set[str] = set()
    for p in paths:
        for path in find_skills(p):
            skill = load(path)
            found.add(skill.name)
            if skill.name not in locked:
                print(f"{skill.name}: not in {lockfile} (new skill)")
                worst = "high"
                continue
            d = lock.diff(locked[skill.name], skill)
            if not d.changes:
                print(f"{skill.name}: unchanged")
                continue
            print(f"{skill.name}: {len(d.changes)} change(s), worst {d.worst}")
            for c in d.changes:
                print(f"  [{c.level:<6}] {c.what}")
                for line in c.detail.splitlines():
                    print(f"           {line}")
            worst = min(worst, d.worst, key=rank.index)
    for name in sorted(set(locked) - found):
        print(f"{name}: in {lockfile} but not found (removed, or not under these paths)")
    return 1 if worst == "high" else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skill-preflight")
    ap.add_argument("--version", action="version", version=f"skill-preflight {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check one skill or a directory of skills")
    c.add_argument("paths", nargs="+", type=Path)
    c.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    c.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    for name, helptext in (("lock", "record hashes and manifests"), ("diff", "compare to lock")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("paths", nargs="+", type=Path)
        s.add_argument(
            "--lockfile",
            type=Path,
            default=Path("skills.lock"),
            help="default: skills.lock in the current directory",
        )
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args.paths, args.strict, args.format)
    if args.cmd == "lock":
        return cmd_lock(args.paths, args.lockfile)
    try:
        return cmd_diff(args.paths, args.lockfile)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
