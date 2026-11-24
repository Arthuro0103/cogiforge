"""Open Agent Skills spec (https://agentskills.io/specification), checked on every .claude/skills/*/SKILL.md.

Rules: frontmatter has `name` and `description`; name is 1-64 chars of a-z 0-9 and hyphen, no leading or
trailing hyphen, no `--`, equal to the folder; description is 1-1024 characters (counted on the parsed
value, not the raw line); SKILL.md stays under 500 lines. A missing skill or an empty glob is a failure:
a check that touched nothing is NOT_VERIFIED, never OK.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
MAX_NAME, MAX_DESC, MAX_LINES = 64, 1024, 500


def parse_frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fields = {}
    for line in m.group(1).split("\n"):
        k = re.match(r"([A-Za-z_-]+):[ \t]*(.*)$", line)
        if not k:
            continue
        v = k.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        fields[k.group(1)] = v
    return fields


def spec_errors(skill_dir):
    """List of spec violations for one skill folder. A folder without SKILL.md is itself a violation."""
    skill_dir = Path(skill_dir)
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return [f"{skill_dir.name}: SKILL.md does not exist"]
    text = md.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm is None:
        return [f"{skill_dir.name}: no frontmatter"]
    errors = []
    name, desc = fm.get("name"), fm.get("description")
    if not name:
        errors.append("no name")
    else:
        if not 1 <= len(name) <= MAX_NAME:
            errors.append(f"name has {len(name)} characters (1-{MAX_NAME})")
        if not re.fullmatch(r"[a-z0-9-]+", name):
            errors.append("name has characters outside a-z 0-9 -")
        if name.startswith("-") or name.endswith("-"):
            errors.append("name starts or ends with a hyphen")
        if "--" in name:
            errors.append("name has a double hyphen")
        if name != skill_dir.name:
            errors.append(f"name {name!r} is not the folder {skill_dir.name!r}")
    if not desc:
        errors.append("no description")
    elif not 1 <= len(desc) <= MAX_DESC:
        errors.append(f"description has {len(desc)} characters (1-{MAX_DESC})")
    lines = len(text.split("\n")) - (1 if text.endswith("\n") else 0)
    if lines >= MAX_LINES:
        errors.append(f"SKILL.md has {lines} lines (under {MAX_LINES})")
    return [f"{skill_dir.name}: {e}" for e in errors]


def skill_dirs(root=SKILLS):
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def require_skills(root=SKILLS):
    """The folders to check; none found is a failure (NOT_VERIFIED), never a pass."""
    found = skill_dirs(root)
    assert found, f"no skill found in {root}: NOT_VERIFIED, not OK"
    return found


def make(tmp_path, name, body=None, folder=None):
    d = tmp_path / (folder or name)
    d.mkdir()
    (d / "SKILL.md").write_text(body if body is not None else f"---\nname: {name}\ndescription: Does x.\n---\nBody\n",
                                encoding="utf-8")
    return d


def test_the_glob_is_not_empty():
    assert len(require_skills()) >= 1


def test_an_empty_or_missing_skills_folder_is_a_failure(tmp_path):
    with pytest.raises(AssertionError):
        require_skills(tmp_path)
    with pytest.raises(AssertionError):
        require_skills(tmp_path / "does-not-exist")


@pytest.mark.parametrize("d", skill_dirs(), ids=lambda d: d.name)
def test_every_skill_follows_the_open_spec(d):
    assert spec_errors(d) == []


def test_a_valid_skill_passes(tmp_path):
    assert spec_errors(make(tmp_path, "cf-ok")) == []


def test_a_missing_skill_fails(tmp_path):
    (tmp_path / "cf-ghost").mkdir()
    assert spec_errors(tmp_path / "cf-ghost")


def test_missing_frontmatter_fields_fail(tmp_path):
    assert spec_errors(make(tmp_path, "cf-a", "---\ndescription: x\n---\n"))
    assert spec_errors(make(tmp_path, "cf-b", "---\nname: cf-b\n---\n"))
    assert spec_errors(make(tmp_path, "cf-c", "no frontmatter\n"))


@pytest.mark.parametrize("bad,fragment", [
    ("cf--x", "double hyphen"), ("-cf", "hyphen"), ("cf-", "hyphen"), ("CF-x", "characters outside"),
    ("cf_x", "characters outside"), ("cf x", "characters outside"), ("a" * 65, "65 characters"),
])
def test_bad_names_fail_for_their_own_reason(tmp_path, bad, fragment):
    # The folder carries the same name, so the only violation is the one under test.
    d = tmp_path / bad
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\nname: {bad}\ndescription: x\n---\n", encoding="utf-8")
    errors = spec_errors(d)
    assert errors and all(fragment in e for e in errors), errors


def test_a_name_that_differs_from_the_folder_fails(tmp_path):
    assert spec_errors(make(tmp_path, "cf-x", folder="cf-y"))


def test_a_name_of_exactly_64_characters_passes(tmp_path):
    n = "a" * 64
    assert spec_errors(make(tmp_path, n)) == []


def test_description_length_is_counted_on_the_parsed_value(tmp_path):
    ok = make(tmp_path, "cf-ok", "---\nname: cf-ok\ndescription: " + "x" * 1024 + "\n---\n")
    over = make(tmp_path, "cf-over", "---\nname: cf-over\ndescription: " + "x" * 1025 + "\n---\n")
    quoted = make(tmp_path, "cf-quoted", '---\nname: cf-quoted\ndescription: "' + "x" * 1024 + '"\n---\n')
    empty = make(tmp_path, "cf-empty", "---\nname: cf-empty\ndescription:\n---\n")
    assert spec_errors(ok) == []
    assert spec_errors(over)
    assert spec_errors(quoted) == []
    assert spec_errors(empty)


def test_a_skill_of_500_lines_fails_and_499_passes(tmp_path):
    head = "---\nname: cf-long\ndescription: x\n---\n"
    assert spec_errors(make(tmp_path, "cf-long", head + "l\n" * (499 - 4))) == []
    d = tmp_path / "cf-long"
    (d / "SKILL.md").write_text(head + "l\n" * (500 - 4), encoding="utf-8")
    assert spec_errors(d)


MAX_DESC_BYTES = 450   # every description loads in EVERY session; the spec allows 1024 characters, the budget does not


def test_every_description_stays_within_the_byte_budget():
    dirs = require_skills()
    too_long = []
    for d in dirs:
        desc = parse_frontmatter((d / "SKILL.md").read_text(encoding="utf-8")).get("description") or ""
        n = len(desc.encode("utf-8"))
        if n > MAX_DESC_BYTES:
            too_long.append(f"{d.name}: {n} bytes (max {MAX_DESC_BYTES})")
    assert not too_long, too_long
