"""The brainstorm pack: three skills (cf-extract-routine, cf-brainstorm, cf-whats-real) and their three templates."""
import re
from pathlib import Path

import pytest

import gate
import ring
from helpers import vault

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
WS = ROOT / "vault" / "skill-worksheets"
NAMES = ["cf-extract-routine", "cf-brainstorm", "cf-whats-real"]
TEMPLATES = ["routine-template", "brainstorm-brief-template", "whats-real-template"]


def skill_text(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    return m.group(1)


@pytest.mark.parametrize("name", NAMES)
def test_skill_has_name_and_description_with_triggers(name):
    fm = frontmatter(skill_text(name))
    assert re.search(rf"^name: {re.escape(name)}$", fm, re.M)
    desc = re.search(r"^description: (.+)$", fm, re.M).group(1)
    assert "TRIGGERS" in desc
    assert "Do NOT trigger" in desc
    assert len(desc) <= 1024


@pytest.mark.parametrize("name", NAMES)
def test_skill_links_its_template(name):
    tpl = {"cf-extract-routine": "routine-template", "cf-brainstorm": "brainstorm-brief-template",
           "cf-whats-real": "whats-real-template"}[name]
    assert f"[[skill-worksheets/{tpl}|" in skill_text(name)


@pytest.mark.parametrize("tpl", TEMPLATES)
def test_template_exists_passes_the_gate_and_is_not_an_orphan(tpl):
    assert (WS / f"{tpl}.md").is_file()
    v = ROOT / "vault"
    scanned, failures = gate.audit(v)
    assert any(Path(p).name == f"{tpl}.md" for p in scanned)
    assert failures == []
    notes, deg = ring.analyze(v)
    assert ring.chk_orphans(notes, deg) == []
    assert deg[f"skill-worksheets/{tpl}.md"] > 0


def test_catalog_lists_the_three_templates():
    cat = (WS / "_catalog.md").read_text(encoding="utf-8")
    for tpl in TEMPLATES:
        assert f"[[skill-worksheets/{tpl}\\|{tpl}]]" in cat


def test_a_template_with_no_inbound_link_fails_the_ring(tmp_path):
    files = {
        "skill-worksheets/_catalog.md": "lists [[skill-worksheets/linked-template]]\n",
        "skill-worksheets/linked-template.md": "linked, body points back to [[skill-worksheets/_catalog]]\n",
        "skill-worksheets/loose-template.md": "---\ntype: brief\n---\n# loose\n\nno link in, none out\n",
    }
    v = vault(tmp_path, files)
    notes, deg = ring.analyze(v)
    assert ring.chk_orphans(notes, deg) == ["skill-worksheets/loose-template.md"]


def test_brainstorm_has_the_hard_gate_and_three_paths():
    t = skill_text("cf-brainstorm")
    assert "HARD-GATE" in t
    assert "3" in t
    assert "approve" in t and "revise" in t and "abort" in t


def test_extract_routine_has_the_three_states():
    t = skill_text("cf-extract-routine")
    for state in ("draft", "ready-for-human-review", "validated"):
        assert state in t
    assert "[CONFIRM]" in t


def test_whats_real_has_the_three_sections():
    for text in (skill_text("cf-whats-real"), (WS / "whats-real-template.md").read_text(encoding="utf-8")):
        for section in ("Works", "Simulated or demo", "Unknown"):
            assert section in text


def test_new_lines_are_in_the_when_to_use_table():
    table = (ROOT / "vault" / "CLAUDE.md").read_text(encoding="utf-8")
    for name in NAMES:
        assert re.search(rf"^\| `{re.escape(name)}` \|", table, re.M)


def test_root_claude_md_stays_under_5_kb():
    assert (ROOT / "CLAUDE.md").stat().st_size < 5 * 1024
