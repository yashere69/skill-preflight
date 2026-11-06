"""Context budget: what this skill costs an agent's context window.

Token counts are estimated at 4 characters per token. That's close enough for English
markdown to compare against the spec's guidance (about 100 tokens of metadata loaded for
every skill, under 5,000 for the body, SKILL.md under 500 lines), and it needs no model
tokenizer. Non-Latin text costs more tokens per character, so treat the numbers as a floor.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .model import Finding, Skill

CHARS_PER_TOKEN = 4
_LINK = re.compile(r"\]\(([^)#\s]+)\)|`((?:scripts|references|assets)/[^`\s]+)`")


def tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


@dataclass
class Budget:
    metadata_tokens: int
    body_tokens: int
    body_lines: int
    resource_tokens: int


def measure(skill: Skill) -> Budget:
    fm = skill.frontmatter or {}
    meta = f"{fm.get('name', '')} {fm.get('description', '')}"
    resources = sum(
        tokens(data.decode("utf-8", "replace"))
        for path, data in skill.files.items()
        if path != "SKILL.md" and path.endswith((".md", ".txt"))
    )
    return Budget(tokens(meta), tokens(skill.body), skill.raw.count("\n") + 1, resources)


def check(skill: Skill) -> Iterator[Finding]:
    b = measure(skill)
    if b.body_tokens > 5000:
        yield Finding(
            "budget.body", "warning",
            f"body is ~{b.body_tokens} tokens; the spec recommends under 5,000 "
            "(move detail into references/)",
        )
    if b.body_lines > 500:
        yield Finding("budget.lines", "warning", f"SKILL.md is {b.body_lines} lines (max 500)")
    if b.metadata_tokens > 300:
        yield Finding(
            "budget.metadata", "info",
            f"name+description is ~{b.metadata_tokens} tokens, loaded for every task",
        )
    for m in _LINK.finditer(skill.body):
        ref = (m.group(1) or m.group(2)).strip()
        if ref.startswith(("http://", "https://", "mailto:")):
            continue
        ref = ref.removeprefix("./")
        if ref not in skill.files and not any(f.startswith(ref.rstrip("/") + "/") for f in
                                              skill.files):
            yield Finding("refs.missing", "error", f"references {ref!r}, which isn't in the skill")
        elif ref.count("/") > 1:
            yield Finding(
                "refs.depth", "info", f"{ref!r} is nested; the spec suggests one level deep"
            )
