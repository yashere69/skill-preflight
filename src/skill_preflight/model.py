"""Load a skill directory: frontmatter, body and the files around it."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}


@dataclass
class Finding:
    rule: str
    level: str  # error | warning | info
    message: str
    where: str = "SKILL.md"


@dataclass
class Skill:
    root: Path
    raw: str
    frontmatter: dict | None
    body: str
    body_line: int  # line in SKILL.md where the body starts
    files: dict[str, bytes] = field(default_factory=dict)  # relative path -> content
    parse_error: str | None = None

    @property
    def name(self) -> str:
        fm = self.frontmatter or {}
        return str(fm.get("name") or self.root.name)


def split_frontmatter(raw: str) -> tuple[str | None, str, int]:
    if not raw.startswith("---"):
        return None, raw, 1
    lines = raw.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :]), i + 2
    return None, raw, 1


def load(root: Path) -> Skill:
    md = root / "SKILL.md"
    raw = md.read_text(encoding="utf-8") if md.exists() else ""
    fm_text, body, body_line = split_frontmatter(raw)
    fm: dict | None = None
    err = None
    if fm_text is not None:
        try:
            loaded = yaml.safe_load(fm_text)
            fm = loaded if isinstance(loaded, dict) else None
            if fm is None:
                err = "frontmatter is not a mapping"
        except yaml.YAMLError as e:
            err = f"frontmatter is not valid YAML: {e}"
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS):
            files[p.relative_to(root).as_posix()] = p.read_bytes()
    return Skill(root, raw, fm, body, body_line, files, err)


def find_skills(target: Path) -> list[Path]:
    if (target / "SKILL.md").exists():
        return [target]
    return sorted(p.parent for p in target.rglob("SKILL.md") if not set(p.parts) & SKIP_DIRS)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
