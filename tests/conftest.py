from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "skills"


@pytest.fixture
def make_skill(tmp_path):
    def make(name="demo-skill", frontmatter=None, body="Do the thing.\n", files=None):
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        fm = (
            frontmatter
            if frontmatter is not None
            else (f"name: {name}\ndescription: Does a thing. Use when asked to do the thing.\n")
        )
        (root / "SKILL.md").write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
        for rel, text in (files or {}).items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return root

    return make
