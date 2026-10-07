"""The context and pains guides: worksheets, CSV templates, docs and the know-my-product skill."""
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import ring
from helpers import vault

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"
WS = VAULT / "worksheets"
NAMES = ["product-brief", "pains", "audience", "project-brief", "decisions-log", "weekly-review"]
CSVS = {"pains": "date", "decisions-log": "decision"}


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)


@pytest.mark.parametrize("name", NAMES)
def test_worksheet_exists_with_valid_frontmatter(name):
    path = WS / f"{name}.md"
    assert path.is_file(), f"{path} is missing"
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\ntype: worksheet\nstatus: [a-z-]+\n---\n\n# ", text)
    assert m, f"{name}: frontmatter must be type: worksheet and a status, then a title"
    assert "## When to use it" in text and "## What Claude does with it" in text


def test_worksheets_pass_the_gate():
    r = run("core/gate.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_worksheets_are_not_orphans_in_the_real_vault():
    r = run("core/ring.py", "--vault", "vault", "--gate")
    assert r.returncode == 0, r.stdout + r.stderr
    notes, degree = ring.analyze(VAULT)
    for name in NAMES:
        assert degree[f"worksheets/{name}.md"] > 0, f"{name} has no link at all"


@pytest.mark.parametrize("name", NAMES)
def test_home_links_every_worksheet(name):
    assert f"[[worksheets/{name}]]" in (VAULT / "home.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name,first", CSVS.items())
def test_csv_has_header_and_opens_with_dictreader(name, first):
    path = WS / "csv" / f"{name}.csv"
    assert path.is_file()
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames and reader.fieldnames[0] == first
        assert all(h and h.strip() for h in reader.fieldnames)
        rows = list(reader)
    assert rows, "the template carries one invented example row"
    assert all(None not in r and all(v is not None for v in r.values()) for r in rows), "ragged row"


def test_guides_exist():
    for rel in ("docs/CONTEXT.md", "docs/PRODUCT-AND-PAINS.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert len(text) > 1500, f"{rel} is too short to be a guide"


def test_skill_has_name_and_description_and_is_in_the_table():
    text = (ROOT / ".claude/skills/know-my-product/SKILL.md").read_text(encoding="utf-8")
    fm = text.split("---")[1]
    assert re.search(r"^name: know-my-product$", fm, re.M)
    desc = re.search(r"^description: (.+)$", fm, re.M)
    assert desc and "TRIGGERS" in desc.group(1) and "Do NOT trigger" in desc.group(1)
    assert "`know-my-product`" in (VAULT / "CLAUDE.md").read_text(encoding="utf-8")


def test_readme_links_the_guides():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Context, worksheets and pains" in readme
    for link in ("docs/CONTEXT.md", "docs/PRODUCT-AND-PAINS.md", "vault/worksheets/"):
        assert link in readme


def test_a_worksheet_with_no_incoming_link_fails_the_ring(tmp_path):
    """Negative test: copy the worksheets to a vault whose home links none of them."""
    v = vault(tmp_path, {"home.md": "# Index\n\nlinks to [[other]]\n", "other.md": "back to [[home]]\n"})
    shutil.copy(WS / "audience.md", v / "audience.md")
    text = (v / "audience.md").read_text(encoding="utf-8")
    (v / "audience.md").write_text(re.sub(r"\[\[[^\]]*\]\]", "x", text), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "core" / "ring.py"), "--vault", str(v), "--gate"],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "audience.md" in r.stdout + r.stderr
