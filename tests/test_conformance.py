import pytest

from skill_preflight.conformance import check
from skill_preflight.model import load


def rules(path):
    return sorted({f.rule for f in check(load(path))})


def test_minimal_skill_conforms(make_skill):
    assert rules(make_skill()) == []


@pytest.mark.parametrize(
    "name, dirname",
    [
        ("PDF-Tools", "PDF-Tools"),
        ("-pdf", "-pdf"),
        ("pdf--tools", "pdf--tools"),
        ("a" * 65, "a" * 65),
    ],
)
def test_bad_names(make_skill, name, dirname):
    root = make_skill(dirname, frontmatter=f"name: '{name}'\ndescription: x\n")
    assert "spec.name" in rules(root)


def test_name_must_match_directory(make_skill):
    root = make_skill("pdf-tools", frontmatter="name: pdf-helper\ndescription: x\n")
    assert rules(root) == ["spec.name-dir"]


def test_unknown_fields_and_types(make_skill):
    root = make_skill(
        frontmatter=(
            "name: demo-skill\ndescription: x\nversion: 2\nmetadata: {a: 1}\n"
            "allowed-tools: [Read, Bash]\ncompatibility: ''\n"
        )
    )
    assert rules(root) == [
        "spec.allowed-tools",
        "spec.compatibility",
        "spec.fields",
        "spec.metadata",
    ]


def test_description_limits(make_skill):
    assert "spec.description" in rules(make_skill(frontmatter="name: demo-skill\n"))
    long = "x" * 1025
    assert "spec.description" in rules(
        make_skill(frontmatter=f"name: demo-skill\ndescription: {long}\n")
    )


def test_missing_or_broken_frontmatter(make_skill, tmp_path):
    root = tmp_path / "no-fm"
    root.mkdir()
    (root / "SKILL.md").write_text("# just markdown\n")
    assert rules(root) == ["spec.frontmatter"]
    bad = make_skill(frontmatter="name: [unclosed\n")
    assert rules(bad) == ["spec.frontmatter"]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert rules(empty) == ["spec.skill-md"]
