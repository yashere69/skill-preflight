"""What the skill's scripts and instructions can do, compared with what it declares.

This is a manifest, not a malware verdict. Pattern matching finds `curl` and
`os.environ`; it can't find intent, and anything written to evade it will. The output is
for a human deciding whether to install, and for `diff` to notice when the manifest grows.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from .model import Finding, Skill

SCRIPT_EXT = (".py", ".sh", ".bash", ".js", ".mjs", ".ts", ".rb", ".ps1")

PATTERNS: dict[str, list[str]] = {
    "network": [
        r"\bcurl\b", r"\bwget\b", r"\brequests\.", r"\burllib\b", r"\bhttpx\b", r"\bfetch\(",
        r"\baxios\b", r"Invoke-WebRequest", r"\bsocket\.", r"https?://",
    ],
    "shell": [
        r"\bsubprocess\b", r"\bos\.system\b", r"\bos\.popen\b", r"\bchild_process\b",
        r"\bexecSync\b", r"\beval\(", r"\bexec\(", r"\bbash -c\b",
    ],
    "env": [r"\bos\.environ\b", r"\bgetenv\(", r"\bprocess\.env\b", r"\$\{?[A-Z_]{3,}\}?"],
    "credentials": [
        r"\.ssh/", r"\.aws/", r"id_rsa", r"\.netrc", r"\.npmrc", r"\.git-credentials",
        r"keychain", r"\bAPI_KEY\b", r"\bTOKEN\b", r"\bSECRET\b",
    ],
    "writes-outside": [r"~/", r"\$HOME", r"/etc/", r"expanduser\(", r"Path\.home\("],
}
_COMPILED = {k: [re.compile(p) for p in v] for k, v in PATTERNS.items()}

# which allowed-tools entries count as declaring a capability
DECLARES = {
    "network": re.compile(r"WebFetch|WebSearch|Bash\((curl|wget)", re.I),
    "shell": re.compile(r"\bBash\b", re.I),
}


def observed(skill: Skill) -> dict[str, list[str]]:
    """capability -> files where it appears"""
    found: dict[str, list[str]] = {}
    for path, data in skill.files.items():
        if not path.endswith(SCRIPT_EXT):
            continue
        text = data.decode("utf-8", "replace")
        for cap, rxs in _COMPILED.items():
            if any(rx.search(text) for rx in rxs):
                found.setdefault(cap, []).append(path)
    return found


def check(skill: Skill) -> Iterator[Finding]:
    obs = observed(skill)
    declared = str((skill.frontmatter or {}).get("allowed-tools") or "")
    for cap, files in sorted(obs.items()):
        where = ", ".join(files)
        if declared and cap in DECLARES and not DECLARES[cap].search(declared):
            yield Finding(
                f"cap.{cap}", "warning",
                f"scripts use {cap} but allowed-tools doesn't declare it", where,
            )
        else:
            level = "warning" if cap in {"credentials", "writes-outside"} else "info"
            yield Finding(f"cap.{cap}", level, f"scripts use {cap}", where)
