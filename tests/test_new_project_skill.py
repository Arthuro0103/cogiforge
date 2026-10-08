"""The cf-new-project skill: one question at a time, the target is the user's, a "yes" before creating."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude/skills/cf-new-project/SKILL.md"


def skill():
    return SKILL.read_text(encoding="utf-8")


def test_frontmatter_has_name_triggers_and_do_not_trigger():
    fm = skill().split("---")[1]
    assert re.search(r"^name: cf-new-project$", fm, re.M)
    assert "TRIGGERS" in fm and "Do NOT trigger" in fm
    desc = re.search(r"^description: (.+)$", fm, re.M).group(1)
    assert len(desc) <= 1024, len(desc)
    for stay_out in ("already exists", "existing base", "adopt"):
        assert stay_out in fm


def test_asks_one_thing_at_a_time_and_waits():
    t = skill()
    assert "**One question per message.**" in t
    assert t.count("**STOP and wait.**") >= 4


def test_questions_come_in_the_expected_order():
    t = skill()
    name_q = t.index("### 1. The name")
    target_q = t.index("What exists in the world when this project works out?")
    type_q = t.index("### 3. Type and status")
    dry = t.index("--dry-run\n```")
    assert name_q < target_q < type_q < dry


def test_target_is_the_users_sentence_word_for_word():
    t = skill()
    assert "word for word" in t
    assert "Never invent it" in t
    assert "unchanged: no fixing" in re.sub(r"\s+", " ", t).replace("unchanged: no fixing,", "unchanged: no fixing")
    assert "no translating" in re.sub(r"\s+", " ", t)
    assert "Invent, complete, fix or translate the target." in t


def test_nothing_is_created_before_the_yes():
    t = skill()
    assert "**Never create without the \"yes\".**" in t
    assert t.index("--dry-run\n```") < t.index("Create it? (yes/no)") < t.index("### 5. Create (command, only after the \"yes\")")


def test_nothing_is_written_about_the_user_that_they_did_not_say():
    t = skill()
    assert "**Never write about the user what they did not say**" in t
    assert "Fill the other sections of `instructions.md` for the user." in t


def test_gate_and_ring_are_run_and_their_rc_reported():
    t = skill()
    assert "python3 core/gate.py" in t and "python3 core/ring.py --vault vault --gate" in t
    assert "Say \"done\" without having run `gate` and `ring`" in t


def test_the_tool_it_calls_exists():
    assert (ROOT / "tools/new_project.py").is_file()
    assert "python3 tools/new_project.py" in skill()
