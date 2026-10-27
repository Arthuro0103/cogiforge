"""The cf-new-rule skill: no dated mistake, no rule; the test is seen red first; nothing outside vault/ without a yes."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude/skills/cf-new-rule/SKILL.md"


def skill():
    return SKILL.read_text(encoding="utf-8")


def test_frontmatter_has_name_triggers_and_do_not_trigger():
    fm = skill().split("---")[1]
    assert re.search(r"^name: cf-new-rule$", fm, re.M)
    assert "TRIGGERS" in fm and "Do NOT trigger" in fm
    desc = re.search(r"^description: (.+)$", fm, re.M).group(1)
    assert len(desc) <= 1024, len(desc)
    for stay_out in ("has not happened yet", "cf-task-observer", "cf-adapt-skill", "cf-whats-real"):
        assert stay_out in fm


def test_asks_one_question_at_a_time():
    assert "1. **One question per message.**" in skill()


def test_no_dated_mistake_no_rule_and_nothing_invented():
    t = skill()
    assert "2. **No mistake, no rule.**" in t
    assert "**Nothing is deduced.**" in t
    assert "Never invent an incident" in t
    assert "Write a rule from a mistake that has not happened" in t


def test_the_red_test_comes_before_the_rule_and_is_a_pair():
    t = skill()
    assert "4. **The test comes before the rule.**" in t
    assert "5. **A pair, always.**" in t
    assert t.index("### 3. The pair and the red test") < t.index("### 4. The rule") < t.index("### 5. The mutation")
    assert "Write the rule before the red test" in t


def test_nothing_outside_vault_is_written_without_a_yes():
    t = skill()
    assert "6. **Never write outside `vault/` on your own.**" in t
    assert t.index("Write these in the repo? (yes/no)") < t.index("### 7. Run the gates")
    assert "Edit `core/`, `tests/`, `WHY.md`, `CLAUDE.md` or `AGENTS.md` without the user's \"yes\"" in t


def test_claude_md_size_cap_and_no_bypass():
    t = skill()
    assert "7. **`CLAUDE.md` stays under 5 KB.**" in t and "wc -c CLAUDE.md" in t
    assert "**Never use `--no-verify`**" in t


def test_unproven_is_not_verified_and_gates_are_run():
    t = skill()
    assert "NOT_VERIFIED" in t
    for cmd in ("python3 core/gate.py", "python3 core/ring.py --vault vault --gate", "python3 core/leak.py .", "python3 -m pytest -q"):
        assert cmd in t


def test_it_is_listed_for_other_agents_and_in_the_readme():
    assert "cf-new-rule" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "/cf-new-rule" in (ROOT / "README.md").read_text(encoding="utf-8")
