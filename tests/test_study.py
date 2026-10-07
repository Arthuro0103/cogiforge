"""The study skill, its two worksheets, the student guide and the table line."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

import ring
from helpers import vault

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"
SKILL = ROOT / ".claude/skills/cf-study/SKILL.md"
TEMPLATES = ["study-plan-template", "mastery-template"]


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)


def skill():
    return SKILL.read_text(encoding="utf-8")


def test_skill_has_name_description_triggers_and_not_triggers():
    fm = skill().split("---")[1]
    assert re.search(r"^name: cf-study$", fm, re.M)
    desc = re.search(r"^description: (.+)$", fm, re.M)
    assert desc and "TRIGGERS" in desc.group(1) and "Do NOT trigger" in desc.group(1)


def test_skill_has_both_states_and_the_retest_on_another_day_rule():
    t = skill()
    assert "`learning`" in t and "`mastered`" in t
    assert re.search(r"RETEST on a\s+different day", t)


def test_skill_forbids_claiming_mastery_without_proof():
    t = skill()
    assert "Never claim the student knows something without proof" in t
    assert "Never invent a source" in t and "[VERIFY]" in t


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_exists_with_frontmatter(name):
    text = (VAULT / "skill-worksheets" / f"{name}.md").read_text(encoding="utf-8")
    assert re.match(r"---\ntype: [a-z-]+\nstatus: [a-z-]+\n", text)


def test_catalog_lists_both_templates():
    cat = (VAULT / "skill-worksheets/_catalog.md").read_text(encoding="utf-8")
    for name in TEMPLATES:
        assert f"[[skill-worksheets/{name}\\|{name}]]" in cat


def test_gate_and_ring_pass_and_templates_are_not_orphans():
    assert run("core/gate.py", "--vault", "vault").returncode == 0
    r = run("core/ring.py", "--vault", "vault", "--gate")
    assert r.returncode == 0, r.stdout + r.stderr
    _, degree = ring.analyze(VAULT)
    for name in TEMPLATES:
        assert degree[f"skill-worksheets/{name}.md"] > 0


def test_template_without_an_inbound_link_fails_the_ring(tmp_path):
    body = (VAULT / "skill-worksheets/mastery-template.md").read_text(encoding="utf-8")
    body = re.sub(r"\[\[[^\]]*\]\]", "plain text", body)
    v = vault(tmp_path, {"a.md": "[[b]]\n", "b.md": "[[a]]\n", "skill-worksheets/mastery-template.md": body})
    notes, deg = ring.analyze(v)
    assert "skill-worksheets/mastery-template.md" in ring.chk_orphans(notes, deg)


def test_vault_claude_md_has_the_study_row():
    t = (VAULT / "CLAUDE.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `cf-study` \|", t, re.M)


def test_students_guide_and_readme_link():
    assert (ROOT / "docs/STUDENTS.md").is_file()
    assert "docs/STUDENTS.md" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_root_claude_md_stays_under_5_kb():
    assert (ROOT / "CLAUDE.md").stat().st_size < 5 * 1024
