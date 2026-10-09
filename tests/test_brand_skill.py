"""The cf-brand skill: one question at a time, only the user's words, a "yes" before saving, two voice modes,
a manual that only assembles, and templates that carry no default color."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude/skills/cf-brand/SKILL.md"
WS = ROOT / "vault" / "skill-worksheets"
TEMPLATES = ["brand-voice", "brand-dna", "brand-messaging", "brand-design"]
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")


def skill():
    return SKILL.read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text)


def section(text, start, end):
    return text[text.index(start):text.index(end)]


def test_frontmatter_has_name_triggers_and_do_not_trigger():
    fm = skill().split("---")[1]
    assert re.search(r"^name: cf-brand$", fm, re.M)
    desc = re.search(r"^description: (.+)$", fm, re.M).group(1)
    assert len(desc) <= 1024, len(desc)
    assert "TRIGGERS" in desc and "Do NOT trigger" in desc
    after = desc[desc.index("Do NOT trigger"):]
    for other in ("cf-onboard", "cf-know-my-product", "cf-new-project", "decision, not an interview"):
        assert other in after, other


def test_has_the_sections_of_a_cogiforge_skill():
    t = skill()
    for heading in ("## Why it exists", "## The rules", "## The modes", "## The steps", "## Never"):
        assert heading in t, heading


@pytest.mark.parametrize("mode", ["voice --person", "voice --project <name>", "dna <name>", "messaging <name>",
                                  "design <name>", "manual <name>"])
def test_every_mode_is_in_the_table(mode):
    assert f"`/cf-brand {mode}`" in section(skill(), "## The modes", "## The steps")


def test_asks_one_thing_at_a_time():
    t = skill()
    assert "**One question per message.**" in t
    assert "Never a list." in t


def test_nothing_is_saved_before_the_yes():
    t = flat(skill())
    assert "**Never write without the \"yes\".**" in t
    assert "save only after the yes" in t
    assert "**STOP and wait.**" in t
    assert "Save before the \"yes\"." in t


def test_only_the_users_words_and_nothing_deduced():
    t = flat(skill())
    assert "**Nothing deduced.**" in t
    assert "record \"chose option X\", with no quotation marks" in t
    assert "Write about the person or the project something they did not say" in t


def test_voice_has_two_modes_and_the_project_one_inherits():
    t = skill()
    person = section(t, "### 1. `voice --person`", "### 2.")
    project = section(t, "### 2. `voice --project <name>`", "### 3.")
    assert "vault/memory/voice.md" in person and "scope: person" in person
    assert "inherits: vault/memory/voice.md" in project and "scope: project" in project
    assert "**what differs**" in flat(project)
    assert "Never copy the person's lines into the project file" in flat(project)
    assert "do not invent a base" in flat(project)


def test_voice_file_contract_is_the_one_the_tool_reads():
    t = skill()
    for heading in ("## Phrases", "## Never say", "## Avoid", "## Pairs"):
        assert heading in t, heading
    assert '- YYYY-MM-DD | "literal quote"' in t
    assert '- say: "..." | not: "..."' in t
    assert "type: voice" in t


def test_team_mode_follows_cf_onboard():
    t = skill()
    assert "vault/people/<handle>/memory/voice.md" in t
    onboard = (ROOT / ".claude/skills/cf-onboard/SKILL.md").read_text(encoding="utf-8")
    assert "vault/people/<handle>/memory/" in onboard
    assert "Never open another person's folder." in t


def test_manual_asks_no_question_and_never_invents():
    m = flat(section(skill(), "### 6. `manual <name>`", "### 7."))
    assert "asks no interview question" in m
    assert "The only question this mode asks is the yes to save the draft." in m
    assert "marked `empty`" in m
    assert "**Never invent**" in m
    assert "never link a file that does not exist" in m
    assert "**asks no interview question**" in section(skill(), "## The modes", "## The steps")


def test_design_has_no_default_color_and_never_picks_for_the_user():
    t = skill()
    design = flat(section(t, "### 5. `design <name>`", "### 6."))
    assert "Never pick it for them." in design
    assert "never filled with a default" in design
    assert "**The template carries nothing of anyone.** No default color" in flat(t)
    assert not HEX.search(t), "the skill carries a real color value"


def test_tokens_contract_includes_pairs():
    design = section(skill(), "### 5. `design <name>`", "### 6.")
    block = design[design.index("```json"):]
    for key in ('"name"', '"colors"', '"type"', '"heading"', '"body"', '"space"', '"radius"', '"pairs"'):
        assert key in block, key


def test_voice_check_rc3_is_never_reported_as_clean():
    t = flat(skill())
    assert "python3 tools/voice_check.py" in t
    assert "rc 3: `NOT_VERIFIED`" in t
    assert "Never report rc 3 as clean." in t
    assert "python3 tools/brand_preview.py" in t


def test_no_network_and_gate_ring_after_saving():
    t = skill()
    assert "Call a network service or an API" in t
    assert "python3 core/gate.py" in t and "python3 core/ring.py --vault vault --gate" in t


@pytest.mark.parametrize("tpl", TEMPLATES)
def test_template_exists_is_linked_and_has_no_default_color(tpl):
    path = WS / f"{tpl}.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), tpl
    assert not HEX.search(text), f"{tpl} carries a default color"
    assert "[[skill-worksheets/_catalog|catalog]]" in text
    assert f"[[skill-worksheets/{tpl}\\|{tpl}]]" in (WS / "_catalog.md").read_text(encoding="utf-8")
    assert f"[[skill-worksheets/{tpl}" in skill()


def test_voice_template_has_the_four_sections_and_no_rule_lines():
    text = (WS / "brand-voice.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (.+)$", text, re.M)
    assert heads == ["Phrases", "Never say", "Avoid", "Pairs"]
    body = text[text.index("## Phrases"):]
    assert not re.search(r"^- ", body, re.M), "a blank template must not carry a rule"


def test_design_template_tokens_block_is_empty_json():
    text = (WS / "brand-design.md").read_text(encoding="utf-8")
    raw = re.search(r"```json\n(.*?)```", text, re.S).group(1)
    data = json.loads(raw)
    assert data["colors"] == {} and data["pairs"] == []
    assert set(data) <= {"name", "colors", "type", "space", "radius", "pairs"}


def test_the_guide_is_honest_and_linked():
    doc = (ROOT / "docs/BRAND.md").read_text(encoding="utf-8")
    assert "It does not create an identity on its own." in doc
    assert "no default palette" in doc.lower()
    assert "docs/BRAND.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/BRAND.md" in skill()


@pytest.mark.parametrize("rel", ["README.md", "CLAUDE.md", "AGENTS.md", "vault/CLAUDE.md"])
def test_the_skill_is_listed(rel):
    assert "cf-brand" in (ROOT / rel).read_text(encoding="utf-8")
