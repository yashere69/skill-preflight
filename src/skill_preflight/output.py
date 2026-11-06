"""Machine-readable output: JSON for scripts, SARIF for GitHub code scanning.

SARIF is what makes findings show up as annotations on a pull request and in the repo's
Security tab, via github/codeql-action/upload-sarif. It's the difference between a CI log
someone has to read and a comment on the line that changed.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .budget import Budget
from .model import Finding

SARIF_LEVEL = {"error": "error", "warning": "warning", "info": "note"}
RULE_GROUPS = {
    "spec": "Agent Skills specification conformance",
    "budget": "Context budget",
    "refs": "Files referenced from SKILL.md",
    "cap": "Capability used by the skill's scripts",
    "instr": "Risky instruction in SKILL.md prose",
    "link": "Symbolic link inside the skill",
}


def _location(skill_path: Path, where: str) -> tuple[str, int | None]:
    file, _, line = where.partition(":")
    return (skill_path / file).as_posix(), int(line) if line.isdigit() else None


def to_json(results: list[tuple[Path, list[Finding], Budget]]) -> str:
    return json.dumps(
        [
            {
                "skill": path.name,
                "path": path.as_posix(),
                "budget": vars(b),
                "findings": [vars(f) for f in findings],
            }
            for path, findings, b in results
        ],
        indent=2,
    )


def to_sarif(results: list[tuple[Path, list[Finding], Budget]]) -> str:
    rules: set[str] = set()
    sarif_results = []
    for path, findings, _ in results:
        for f in findings:
            rules.add(f.rule)
            uri, line = _location(path, f.where)
            region = {"startLine": line} if line else {}
            sarif_results.append(
                {
                    "ruleId": f.rule,
                    "level": SARIF_LEVEL[f.level],
                    "message": {"text": f.message},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri},
                                **({"region": region} if region else {}),
                            }
                        }
                    ],
                }
            )
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skill-preflight",
                        "version": __version__,
                        "informationUri": "https://github.com/yashere69/skill-preflight",
                        "rules": [
                            {
                                "id": r,
                                "shortDescription": {"text": RULE_GROUPS.get(r.split(".")[0], r)},
                            }
                            for r in sorted(rules)
                        ],
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(doc, indent=2)
