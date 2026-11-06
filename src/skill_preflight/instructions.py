"""Instruction-level red flags in SKILL.md prose.

Skills are instructions to an agent, so the riskiest line can be plain English: "run this
installer", "don't mention this to the user". Phrases inside code fences or block quotes
are usually examples (a security skill quoting attacks), so they're reported as info
instead of warnings. That keeps a defensive skill from looking like an attack.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from .model import Finding, Skill

RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("instr.pipe-to-shell", "pipes a download into a shell",
     re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b", re.I)),
    ("instr.override", "tries to override other instructions",
     re.compile(r"ignore (all |any )?(previous|prior|other) (instructions|rules)", re.I)),
    ("instr.conceal", "asks the agent to hide something from the user",
     re.compile(r"(do not|don't|never) (tell|inform|mention|show)[^.\n]{0,40}\buser\b", re.I)),
    ("instr.exfil", "asks the agent to send data somewhere",
     re.compile(r"\b(send|post|upload|forward)\b[^.\n]{0,60}\b(to|at)\b[^.\n]{0,40}https?://",
                re.I)),
    ("instr.secrets", "asks the agent to read secrets",
     re.compile(r"\b(read|cat|print|copy)\b[^.\n]{0,40}(\.env\b|id_rsa|\.ssh|credentials|"
                r"api[_ ]?key|token)", re.I)),
    ("instr.paste-site", "links to a paste or raw-file host",
     re.compile(r"https?://(pastebin\.com|paste\.ee|hastebin|gist\.githubusercontent\.com|"
                r"raw\.githubusercontent\.com)", re.I)),
    ("instr.encoded", "contains a long base64-looking blob",
     re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
]

_FENCE = re.compile(r"^\s*(```|~~~)")


def _quoted_lines(body: str) -> set[int]:
    quoted, inside = set(), False
    for i, line in enumerate(body.split("\n")):
        if _FENCE.match(line):
            inside = not inside
            quoted.add(i)
            continue
        if inside or line.lstrip().startswith(">"):
            quoted.add(i)
    return quoted


def check(skill: Skill) -> Iterator[Finding]:
    quoted = _quoted_lines(skill.body)
    lines = skill.body.split("\n")
    for rule, label, rx in RULES:
        for i, line in enumerate(lines):
            if rx.search(line):
                where = f"SKILL.md:{skill.body_line + i}"
                if i in quoted:
                    yield Finding(rule, "info", f"quoted example {label}", where)
                else:
                    yield Finding(rule, "warning", f"instruction {label}", where)
