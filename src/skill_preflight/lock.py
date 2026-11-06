"""skills.lock: pin what you reviewed, and see exactly what an update changes.

A skill can turn hostile without touching a single script: rewrite the description so
the agent loads it for every task, add one sentence that says to fetch a URL. Hashes
catch that something changed; `diff` says what, and ranks the changes that matter.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import capabilities
from .model import Skill, sha256

LOCK_VERSION = 1

_URL = re.compile(r"https?://[^\s)>\]\"']+")
_RISKY_WORDS = re.compile(
    r"\b(always|every task|all tasks|any task|before anything|automatically|silently|"
    r"without (asking|telling)|do not (tell|mention)|don't (tell|mention)|run|execute|install|"
    r"download|fetch|upload|send|post|credentials?|secrets?|tokens?|api keys?|ssh)\b|\.env\b",
    re.I,
)


def entry(skill: Skill) -> dict:
    fm = skill.frontmatter or {}
    return {
        "description": fm.get("description", ""),
        "allowed_tools": fm.get("allowed-tools", ""),
        "files": {p: sha256(d) for p, d in skill.files.items()},
        "capabilities": sorted(capabilities.observed(skill)),
        "urls": sorted(set(_URL.findall(skill.raw))),
    }


def write(path: Path, skills: list[Skill]) -> None:
    data = {"version": LOCK_VERSION, "skills": {s.name: entry(s) for s in skills}}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != LOCK_VERSION:
        raise ValueError(f"{path}: unsupported lock version {data.get('version')}")
    return data["skills"]


@dataclass
class Change:
    level: str  # high | medium | low
    what: str
    detail: str = ""


@dataclass
class SkillDiff:
    name: str
    changes: list[Change] = field(default_factory=list)

    @property
    def worst(self) -> str:
        order = ["high", "medium", "low"]
        return min((c.level for c in self.changes), key=order.index, default="none")


def _risky(text: str) -> set[str]:
    return {m.group(0).lower() for m in _RISKY_WORDS.finditer(text)}


def _new_words(old: str, new: str) -> set[str]:
    return _risky(new) - _risky(old)


def _changed_part(old: str, new: str) -> str:
    """Trim the shared start and end so the reviewer sees only what moved."""
    a, b = old.split(" "), new.split(" ")
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    lead = "... " if i else ""
    old_mid = " ".join(a[i : len(a) - j])
    new_mid = " ".join(b[i : len(b) - j])
    return f"- {lead}{old_mid}\n+ {lead}{new_mid}"


def description_change(old: str, new: str) -> Change:
    words = _new_words(old, new)
    urls = set(_URL.findall(new)) - set(_URL.findall(old))
    ratio = difflib.SequenceMatcher(None, old, new).ratio()
    detail = _changed_part(old, new)
    if urls:
        return Change("high", f"description now links {sorted(urls)}", detail)
    if words:
        return Change("high", f"description adds {sorted(words)}", detail)
    if ratio < 0.6:
        return Change("medium", "description largely rewritten", detail)
    return Change("low", "description edited", detail)


def diff(locked: dict, current: Skill) -> SkillDiff:
    now = entry(current)
    d = SkillDiff(current.name)
    if locked["description"] != now["description"]:
        d.changes.append(description_change(locked["description"], now["description"]))
    if locked["allowed_tools"] != now["allowed_tools"]:
        d.changes.append(
            Change(
                "high",
                "allowed-tools changed",
                f"{locked['allowed_tools']!r} -> {now['allowed_tools']!r}",
            )
        )
    for cap in sorted(set(now["capabilities"]) - set(locked["capabilities"])):
        d.changes.append(Change("high", f"new capability: {cap}"))
    for url in sorted(set(now["urls"]) - set(locked["urls"])):
        d.changes.append(Change("high", f"new URL: {url}"))
    old_files, new_files = locked["files"], now["files"]
    for p in sorted(set(new_files) - set(old_files)):
        level = "high" if p.endswith(capabilities.SCRIPT_EXT) else "medium"
        d.changes.append(Change(level, f"file added: {p}"))
    for p in sorted(set(old_files) - set(new_files)):
        d.changes.append(Change("low", f"file removed: {p}"))
    for p in sorted(set(old_files) & set(new_files)):
        if old_files[p] != new_files[p] and p != "SKILL.md":
            level = "medium" if p.endswith(capabilities.SCRIPT_EXT) else "low"
            d.changes.append(Change(level, f"file changed: {p}"))
    if old_files.get("SKILL.md") != new_files.get("SKILL.md") and not any(
        c.what.startswith("description") for c in d.changes
    ):
        d.changes.append(Change("low", "SKILL.md body changed"))
    return d
