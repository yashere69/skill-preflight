import json
import os

from skill_preflight import lock
from skill_preflight.cli import main
from skill_preflight.model import load

from .conftest import EXAMPLES


def test_symlink_leaving_the_skill_is_an_error_and_never_read(make_skill, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")
    root = make_skill()
    os.symlink(secret, root / "notes.md")
    os.symlink("SKILL.md", root / "alias.md")
    skill = load(root)
    assert "notes.md" not in skill.files and "alias.md" not in skill.files
    assert skill.escaping_links == ["notes.md"]
    assert main(["check", str(root)]) == 1


def test_relinking_is_a_high_change(make_skill, tmp_path):
    root = make_skill()
    os.symlink("SKILL.md", root / "alias.md")
    locked = lock.entry(load(root))
    (root / "alias.md").unlink()
    os.symlink("/etc/hostname", root / "alias.md")
    d = lock.diff(locked, load(root))
    assert d.worst == "high"
    assert any("retargeted" in c.what for c in d.changes)


def test_json_output(capsys):
    assert main(["check", str(EXAMPLES / "release-notes"), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["skill"] == "release-notes"
    assert {f["rule"] for f in data[0]["findings"]} >= {"instr.pipe-to-shell", "cap.network"}


def test_sarif_output_shape(capsys):
    assert main(["check", str(EXAMPLES), "--format", "sarif"]) == 1  # Invoice_Helper errors
    sarif = json.loads(capsys.readouterr().out)
    run = sarif["runs"][0]
    assert sarif["version"] == "2.1.0" and run["tool"]["driver"]["name"] == "skill-preflight"
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert {r["ruleId"] for r in run["results"]} == rule_ids
    pipe = next(
        r
        for r in run["results"]
        if r["ruleId"] == "instr.pipe-to-shell" and r["level"] == "warning"
    )
    loc = pipe["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"].endswith("release-notes/SKILL.md")
    assert loc["region"]["startLine"] == 10
    assert {r["level"] for r in run["results"]} <= {"error", "warning", "note"}
