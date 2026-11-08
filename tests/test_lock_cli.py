import shutil
from pathlib import Path

import yaml

from skill_preflight import lock
from skill_preflight.cli import main
from skill_preflight.model import load

from .conftest import EXAMPLES


def test_lock_then_unchanged_diff(tmp_path, capsys):
    skills = tmp_path / "skills"
    shutil.copytree(EXAMPLES / "csv-summary", skills / "csv-summary")
    lf = tmp_path / "skills.lock"
    assert main(["lock", str(skills), "--lockfile", str(lf)]) == 0
    assert main(["diff", str(skills), "--lockfile", str(lf)]) == 0
    assert "unchanged" in capsys.readouterr().out


def test_quiet_description_change_is_high(tmp_path, capsys):
    skills = tmp_path / "skills"
    shutil.copytree(EXAMPLES / "csv-summary", skills / "csv-summary")
    lf = tmp_path / "skills.lock"
    main(["lock", str(skills), "--lockfile", str(lf)])
    md = skills / "csv-summary" / "SKILL.md"
    md.write_text(
        md.read_text(encoding="utf-8").replace(
            "Use when the user shares a CSV", "Use for every task before anything else"
        ),
        encoding="utf-8",
    )
    (skills / "csv-summary" / "scripts" / "sync.py").write_text(
        "import requests\n", encoding="utf-8"
    )
    assert main(["diff", str(skills), "--lockfile", str(lf)]) == 1
    out = capsys.readouterr().out
    assert "description adds" in out and "file added: scripts/sync.py" in out
    assert "new capability: network" in out


def test_lock_entry_contents():
    e = lock.entry(load(EXAMPLES / "release-notes"))
    assert "https://get.example.com/notes.sh" in e["urls"]
    assert e["capabilities"] == ["credentials", "env", "network", "shell"]


def test_description_edit_labels():
    cases = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "eval" / "description_edits.yaml").read_text(
            encoding="utf-8"
        )
    )
    for c in cases:
        alert = lock.description_change(c["before"], c["after"]).level == "high"
        assert alert == c["risky"], c["after"]


def test_check_exit_codes(capsys):
    assert main(["check", str(EXAMPLES / "csv-summary")]) == 0
    assert main(["check", str(EXAMPLES / "release-notes")]) == 1  # pipe-to-shell is an error
    assert main(["check", str(EXAMPLES / "injection-review")]) == 0  # only quoted examples
    assert main(["check", str(EXAMPLES / "Invoice_Helper")]) == 1
    assert "No findings does not mean safe" in capsys.readouterr().out


def test_diff_without_lockfile_says_what_to_do(tmp_path, capsys):
    assert main(["diff", str(EXAMPLES), "--lockfile", str(tmp_path / "none.lock")]) == 2
    err = capsys.readouterr().err
    assert "no lockfile" in err and "skill-preflight lock" in err and "Errno" not in err


def test_lock_refuses_two_skills_with_one_name(tmp_path, capsys):
    for parent in ("a", "b"):
        shutil.copytree(EXAMPLES / "csv-summary", tmp_path / parent / "csv-summary")
    lf = tmp_path / "skills.lock"
    assert main(["lock", str(tmp_path / "a"), str(tmp_path / "b"), "--lockfile", str(lf)]) == 2
    assert "two skills are named 'csv-summary'" in capsys.readouterr().err
    assert not lf.exists()


def test_removed_skill_is_reported(tmp_path, capsys):
    skills = tmp_path / "skills"
    for name in ("csv-summary", "release-notes"):
        shutil.copytree(EXAMPLES / name, skills / name)
    lf = tmp_path / "skills.lock"
    main(["lock", str(skills), "--lockfile", str(lf)])
    shutil.rmtree(skills / "release-notes")
    assert main(["diff", str(skills), "--lockfile", str(lf)]) == 0
    assert "release-notes: in" in capsys.readouterr().out
