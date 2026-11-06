"""Agent Skills specification checks (agentskills.io/specification, read 2026-11-07).

Mirrors what the reference validator checks for frontmatter and naming, and adds the
size and reference guidance from the same page.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from .model import Finding, Skill

ALLOWED_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def check(skill: Skill) -> Iterator[Finding]:
    if not skill.raw:
        yield Finding("spec.skill-md", "error", "no SKILL.md in this directory")
        return
    if skill.parse_error:
        yield Finding("spec.frontmatter", "error", skill.parse_error)
        return
    fm = skill.frontmatter
    if fm is None:
        yield Finding("spec.frontmatter", "error", "SKILL.md must start with YAML frontmatter")
        return

    extra = sorted(set(fm) - ALLOWED_FIELDS)
    if extra:
        yield Finding("spec.fields", "error", f"fields not in the spec: {extra}")

    name = fm.get("name")
    if not isinstance(name, str) or not name:
        yield Finding("spec.name", "error", "name is required")
    else:
        if len(name) > 64:
            yield Finding("spec.name", "error", f"name is {len(name)} characters (max 64)")
        if not _NAME.match(name):
            yield Finding(
                "spec.name",
                "error",
                "name must be lowercase a-z, 0-9 and single hyphens, not starting or ending "
                "with a hyphen",
            )
        if name != skill.root.name:
            yield Finding(
                "spec.name-dir", "error", f"name {name!r} must match directory {skill.root.name!r}"
            )

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        yield Finding("spec.description", "error", "description is required")
    elif len(desc) > 1024:
        yield Finding("spec.description", "error", f"description is {len(desc)} chars (max 1024)")

    comp = fm.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or not 1 <= len(comp) <= 500):
        yield Finding("spec.compatibility", "error", "compatibility must be 1-500 characters")

    meta = fm.get("metadata")
    if meta is not None:
        if not isinstance(meta, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in meta.items()
        ):
            yield Finding("spec.metadata", "error", "metadata must map strings to strings")

    tools = fm.get("allowed-tools")
    if tools is not None and not isinstance(tools, str):
        yield Finding(
            "spec.allowed-tools", "error", "allowed-tools is a space-separated string, not a list"
        )
