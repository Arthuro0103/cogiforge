"""The cf-ask skill: the default path stays, and the optional try-first mode is documented as optional."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude/skills/cf-ask/SKILL.md"


def skill():
    return SKILL.read_text(encoding="utf-8")


def test_default_path_rules_are_still_there():
    t = skill()
    assert "Answer only from retrieved passages" in t
    assert "Run `cite` before delivering" in t
    assert "the vault does not cover this" in t.lower()


def test_try_first_is_optional_and_off_by_default():
    t = skill()
    assert "`--try-first`" in t
    assert "**Off by default.**" in t
    fm = t.split("---")[1]
    assert "OPTIONAL MODE" in fm and "--try-first" in fm


def test_try_first_asks_for_the_attempt_before_showing_anything():
    t = skill()
    assert "Do NOT show a passage" in t
    assert "**STOP and wait**" in t
    assert t.index("Do NOT show a passage") < t.index("**STOP and wait**") < t.index("4. Do steps 4 to 6 as usual")


def test_try_first_never_calls_an_attempt_wrong_and_stays_read_only():
    t = skill()
    assert 'never "wrong"' in t
    assert "Read-only, as always" in t
    assert 'or call an attempt "wrong"' in t


def test_description_stays_within_the_limit():
    fm = skill().split("---")[1]
    desc = re.search(r"^description: (.+)$", fm, re.M).group(1)
    assert len(desc) <= 1024, len(desc)
