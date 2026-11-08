"""What the skill's scripts and instructions can do, compared with what it declares.

This is a manifest, not a malware verdict. Python scripts are read with `ast`, so a
capability is reported where the code imports or calls something (`requests`,
`subprocess.run`, `os.environ`), not where a comment or docstring mentions it. Other
languages are pattern-matched after their comments are stripped. Neither finds intent, and
code written to evade it will. The output is for a human deciding whether to install, and
for `diff` to notice when the manifest grows.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator

from .model import Finding, Skill

SCRIPT_EXT = (".py", ".sh", ".bash", ".js", ".mjs", ".ts", ".rb", ".ps1")

PATTERNS: dict[str, list[str]] = {
    "network": [
        r"\bcurl\b",
        r"\bwget\b",
        r"\brequests\b",
        r"\burllib\d?\b",
        r"\bhttpx\b",
        r"\bfetch\(",
        r"\baxios\b",
        r"Invoke-WebRequest",
        r"\bsocket\.",
        r"https?://",
    ],
    "shell": [
        r"\bsubprocess\b",
        r"\bos\.system\b",
        r"\bos\.popen\b",
        r"\bchild_process\b",
        r"\bexecSync\b",
        r"\beval\(",
        r"\bexec\(",
        r"\bbash -c\b",
    ],
    "env": [r"\bos\.environ\b", r"\bgetenv\(", r"\bprocess\.env\b", r"\$\{?[A-Z_]{3,}\}?"],
    "credentials": [
        r"\.ssh/",
        r"\.aws/",
        r"id_rsa",
        r"\.netrc",
        r"\.npmrc",
        r"\.git-credentials",
        r"keychain",
        r"[A-Z_]*(API_KEY|TOKEN|SECRET|PASSWORD)\b",
    ],
    "writes-outside": [r"~/", r"\$HOME", r"/etc/", r"expanduser\(", r"Path\.home\("],
}
_COMPILED = {k: [re.compile(p) for p in v] for k, v in PATTERNS.items()}

# which allowed-tools entries count as declaring a capability
DECLARES = {
    "network": re.compile(r"WebFetch|WebSearch|Bash\((curl|wget)", re.I),
    "shell": re.compile(r"\bBash\b", re.I),
}

# --- Python, by syntax tree ----------------------------------------------------------------

_NET_MODULES = {
    "requests",
    "urllib",
    "urllib3",
    "httpx",
    "aiohttp",
    "socket",
    "http",
    "ftplib",
    "smtplib",
    "websocket",
    "websockets",
    "paramiko",
    "grpc",
}
_SHELL_MODULES = {"subprocess", "pty", "pexpect", "sh", "plumbum"}
_SHELL_CALLS = {
    "os.system",
    "os.popen",
    "os.execv",
    "os.execvp",
    "os.execl",
    "os.spawnv",
    "os.startfile",
    "eval",
    "exec",
    "compile",
    "__import__",
}
_ENV_CALLS = {"os.getenv", "os.environ.get", "os.putenv"}
_SECRET_NAME = re.compile(r"[A-Z0-9_]*(API_KEY|TOKEN|SECRET|PASSWORD)\b")
_SECRET_PATH = re.compile(r"\.ssh/|\.aws/|id_rsa|\.netrc|\.npmrc|\.git-credentials|keychain")
_OUTSIDE = re.compile(r"^(~/|/etc/|\$HOME)")


def _dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _python(source: str) -> dict[str, list[int]] | None:
    """capability -> line numbers, or None if the file doesn't parse."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    hits: dict[str, list[int]] = {}

    def add(cap: str, node: ast.AST) -> None:
        hits.setdefault(cap, []).append(getattr(node, "lineno", 0))

    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                root = name.split(".")[0]
                if root in _NET_MODULES:
                    add("network", node)
                if root in _SHELL_MODULES:
                    add("shell", node)
                if root == "dotenv":
                    add("env", node)
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name in _SHELL_CALLS:
                add("shell", node)
            if name in _ENV_CALLS:
                add("env", node)
            if name in {"os.path.expanduser", "Path.home", "pathlib.Path.home"}:
                add("writes-outside", node)
            if name.endswith("urlopen"):
                add("network", node)
        elif isinstance(node, ast.Attribute) and _dotted(node) == "os.environ":
            add("env", node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            if _SECRET_PATH.search(node.value) or _SECRET_NAME.fullmatch(node.value):
                add("credentials", node)
            if _OUTSIDE.match(node.value):
                add("writes-outside", node)
    return hits


# --- everything else, by pattern after stripping comments ---------------------------------

_LINE_COMMENT = {".sh": "#", ".bash": "#", ".rb": "#", ".ps1": "#", ".py": "#"}
_BLOCK = re.compile(r"/\*.*?\*/", re.S)


def _strip_comments(path: str, text: str) -> str:
    if path.endswith((".js", ".mjs", ".ts")):
        text = _BLOCK.sub(lambda m: "\n" * m.group().count("\n"), text)
        return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.split("\n"))
    mark = next((m for ext, m in _LINE_COMMENT.items() if path.endswith(ext)), None)
    if mark:
        return "\n".join(re.sub(r"(^|\s)#(?!!).*$", "", line) for line in text.split("\n"))
    return text


def _patterns(path: str, text: str) -> dict[str, list[int]]:
    hits: dict[str, list[int]] = {}
    for n, line in enumerate(_strip_comments(path, text).split("\n"), start=1):
        for cap, rxs in _COMPILED.items():
            if any(rx.search(line) for rx in rxs):
                hits.setdefault(cap, []).append(n)
    return hits


def observed_lines(skill: Skill) -> dict[str, dict[str, list[int]]]:
    """capability -> {file: [line, ...]}"""
    found: dict[str, dict[str, list[int]]] = {}
    for path, data in skill.files.items():
        if not path.endswith(SCRIPT_EXT):
            continue
        text = data.decode("utf-8", "replace")
        hits = _python(text) if path.endswith(".py") else None
        if hits is None:  # not Python, or Python that doesn't parse
            hits = _patterns(path, text)
        for cap, lines in hits.items():
            found.setdefault(cap, {})[path] = sorted(set(lines))
    return found


def observed(skill: Skill) -> dict[str, list[str]]:
    """capability -> files where it appears"""
    return {cap: sorted(files) for cap, files in observed_lines(skill).items()}


def check(skill: Skill) -> Iterator[Finding]:
    for rel, target in sorted(skill.links.items()):
        if rel in skill.escaping_links:
            yield Finding(
                "link.escapes", "error", f"symlink points outside the skill: {rel} -> {target}", rel
            )
        else:
            yield Finding("link.internal", "info", f"symlink {rel} -> {target}", rel)
    obs = observed_lines(skill)
    declared = str((skill.frontmatter or {}).get("allowed-tools") or "")
    for cap, files in sorted(obs.items()):
        where = ", ".join(
            f"{f}:{','.join(map(str, lines[:3]))}{'…' if len(lines) > 3 else ''}"
            for f, lines in sorted(files.items())
        )
        if declared and cap in DECLARES and not DECLARES[cap].search(declared):
            yield Finding(
                f"cap.{cap}",
                "warning",
                f"scripts use {cap} but allowed-tools doesn't declare it",
                where,
            )
        else:
            level = "warning" if cap in {"credentials", "writes-outside"} else "info"
            yield Finding(f"cap.{cap}", level, f"scripts use {cap}", where)
