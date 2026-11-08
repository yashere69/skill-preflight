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

RULES: list[tuple[str, str, re.Pattern[str]]] = [  # rule, label, pattern
    (
        "instr.pipe-to-shell",
        "pipes a download into a shell",
        re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b", re.I),
    ),
    (
        "instr.override",
        "tries to override other instructions",
        re.compile(r"ignore (all |any )?(previous|prior|other) (instructions|rules)", re.I),
    ),
    (
        "instr.conceal",
        "asks the agent to hide something from the user",
        re.compile(r"(do not|don't|never) (tell|inform|mention|show)[^.\n]{0,40}\buser\b", re.I),
    ),
    (
        "instr.exfil",
        "asks the agent to send data somewhere",
        re.compile(
            r"\b(send|post|upload|forward)\b[^.\n]{0,60}\b(to|at)\b[^.\n]{0,40}https?://", re.I
        ),
    ),
    (
        "instr.secrets",
        "asks the agent to read secrets",
        re.compile(
            # "token" alone is too common in LLM text ("token-counting", "1,000 tokens"), so
            # only the kinds of token that are secrets count
            r"\b(read|cat|print|copy)\b[^.\n]{0,40}(\.env\b|id_rsa|\.ssh\b|credentials|"
            r"api[_ ]?keys?\b|\b(access|auth|bearer|refresh|secret|session)[ _-]?tokens?\b"
            r"|\b[A-Z][A-Z0-9_]*_(TOKEN|KEY|SECRET)\b)",
            re.I,
        ),
    ),
    (
        "instr.paste-site",
        "links to a paste or raw-file host",
        re.compile(
            r"https?://([a-z0-9-]+\.)*(pastebin\.com|paste\.ee|hastebin|paste\.c-net\.org|"
            r"glot\.io|rentry\.(co|org)|controlc\.com|dpaste\.|privatebin|ghostbin|"
            r"termbin\.com|paste\.rs|0x0\.st|transfer\.sh|gist\.githubusercontent\.com|"
            r"raw\.githubusercontent\.com)",
            re.I,
        ),
    ),
    (
        "instr.exfil-host",
        "points at a request-capture or tunnel host",
        re.compile(
            r"https?://([a-z0-9-]+\.)*(webhook\.site|requestbin|pipedream\.net|"
            r"ngrok(-free)?\.(io|app|dev)|interact\.sh|oast\.(fun|live|me|pro|site)|"
            r"burpcollaborator\.net|beeceptor\.com)",
            re.I,
        ),
    ),
    (
        "instr.upload-cmd",
        "uploads the output of a command",
        # curl/wget sending data that includes $(...) or backticks: the agent would run the
        # command and post its output, e.g. --data "$(cat .env)"
        re.compile(
            r"\b(curl|wget)\b[^\n]*(--data[a-z-]*|-d|-F|--form|--upload-file|-T|--post-data)"
            r"[ =]+[^\n]*(\$\(|`)",
            re.I,
        ),
    ),
    (
        "instr.load-exec",
        "runs a shell command when the skill is loaded",
        # !`command` is expanded before the model reads the text, so nothing decides
        # whether it should run
        re.compile(r"!`[^`\n]+`"),
    ),
    (
        "instr.encoded",
        "contains a long base64-looking blob",
        re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"),
    ),
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


_TAGS = re.compile("[\U000e0000-\U000e007f]+")
_BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
_ZERO_WIDTH = re.compile("[\u200b\u2060\ufeff]")
TEXT_EXT = (
    ".md",
    ".txt",
    ".py",
    ".sh",
    ".bash",
    ".js",
    ".mjs",
    ".ts",
    ".rb",
    ".ps1",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
)


def hidden(skill: Skill) -> Iterator[Finding]:
    """Characters a reviewer can't see but a model reads. Unicode tag characters
    (U+E0000-U+E007F) spell out ASCII invisibly and have no use in a skill, so they are
    an error; the decoded text is shown so a person can judge it. Bidirectional overrides
    can make text display differently from how it's read. ZWJ and ZWNJ are left alone,
    since Indic scripts and emoji need them."""
    for path, data in sorted(skill.files.items()):
        if not path.endswith(TEXT_EXT):
            continue
        text = data.decode("utf-8", "replace")
        tags = list(_TAGS.finditer(text))
        if tags:
            decoded = "".join(chr(ord(c) - 0xE0000) for m in tags for c in m.group())
            shown = decoded.encode("unicode_escape").decode()[:60]
            line = text.count("\n", 0, tags[0].start()) + 1
            yield Finding(
                "instr.hidden",
                "error",
                f'{len(decoded)} invisible Unicode tag characters, reading as "{shown}..."',
                f"{path}:{line}",
            )
        bidi = _BIDI.search(text)
        if bidi:
            line = text.count("\n", 0, bidi.start()) + 1
            yield Finding(
                "instr.bidi",
                "warning",
                "bidirectional control characters can make text display differently from "
                "how it is read",
                f"{path}:{line}",
            )
        zw = [m for m in _ZERO_WIDTH.finditer(text) if m.start() > 0]
        if len(zw) >= 3:
            line = text.count("\n", 0, zw[0].start()) + 1
            yield Finding(
                "instr.zero-width", "warning", f"{len(zw)} zero-width characters", f"{path}:{line}"
            )


# Outside a code block or quote these are errors: nothing a skill legitimately does needs
# them unreviewed. The rest are warnings for a person to read.
ERRORS = {"instr.pipe-to-shell", "instr.upload-cmd", "instr.exfil-host"}


def check(skill: Skill) -> Iterator[Finding]:
    yield from hidden(skill)
    quoted = _quoted_lines(skill.body)
    lines = skill.body.split("\n")
    for rule, label, rx in RULES:
        for i, line in enumerate(lines):
            if rx.search(line):
                where = f"SKILL.md:{skill.body_line + i}"
                if i in quoted:
                    yield Finding(rule, "info", f"quoted example {label}", where)
                else:
                    level = "error" if rule in ERRORS else "warning"
                    yield Finding(rule, level, f"instruction {label}", where)
