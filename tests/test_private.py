"""private.py: vault/private.txt becomes Claude Code read-deny rules, and install.sh applies them safely.

What this proves OFFLINE is the derivation and the safe merge. Whether Claude Code then really refuses to
read the files is a property of Claude Code itself and is not testable here (see docs/PRIVATE.md).
"""
import json
import subprocess
from pathlib import Path

import pytest

import private
from test_hook_e2e import clone, sh  # noqa: F401  (fixture)

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "private.py"


def settings(repo):
    return json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))


def deny(repo):
    return settings(repo)["permissions"]["deny"]


# ---- unit ------------------------------------------------------------------------

def test_parse_skips_comments_blanks_and_duplicates():
    assert private.parse("# c\n\n a/** # x\na/**\nb.md\n") == ["a/**", "b.md"]


@pytest.mark.parametrize("bad", ["/abs", "~/x", "!neg", "C:/x", "a\\b", "../x", "a/../b"])
def test_parse_refuses_what_it_cannot_anchor_inside_vault(bad):
    with pytest.raises(private.PrivateError):
        private.parse(bad)


def test_rules_are_read_rules_anchored_at_the_project_root():
    assert private.rules(["people/*/private/**"]) == ["Read(/vault/people/*/private/**)"]


def test_merge_keeps_foreign_rules_and_never_duplicates():
    data = {"permissions": {"deny": ["Bash(rm *)"], "allow": ["Read"]}, "model": "x"}
    data, added = private.merge(data, ["Read(/vault/a)"])
    data, again = private.merge(data, ["Read(/vault/a)"])
    assert added == ["Read(/vault/a)"] and again == []
    assert data["permissions"]["deny"] == ["Bash(rm *)", "Read(/vault/a)"]
    assert data["permissions"]["allow"] == ["Read"] and data["model"] == "x"


def test_selftest_passes():
    r = subprocess.run(["python3", str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- install.sh in a temporary clone ---------------------------------------------

def test_the_template_ships_the_default_rule():
    root = SCRIPT.parent.parent
    assert private.parse((root / "vault" / "private.txt").read_text(encoding="utf-8")) == ["people/*/private/**"]


def test_install_writes_exactly_the_rules_derived_from_private_txt(clone):
    assert deny(clone) == ["Read(/vault/people/*/private/**)"]
    (clone / "vault" / "private.txt").write_text("# mine\npeople/*/private/**\nnotes/health/**\ndiary.md\n", encoding="utf-8")
    r = sh(clone, "sh", "install.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    assert deny(clone) == ["Read(/vault/people/*/private/**)", "Read(/vault/notes/health/**)", "Read(/vault/diary.md)"]


def test_install_twice_is_byte_identical(clone):
    first = (clone / ".claude" / "settings.json").read_bytes()
    assert sh(clone, "sh", "install.sh").returncode == 0
    assert (clone / ".claude" / "settings.json").read_bytes() == first


def test_install_keeps_the_rules_the_user_already_had(clone):
    path = clone / ".claude" / "settings.json"
    path.write_text(json.dumps({"permissions": {"deny": ["Bash(curl *)"], "allow": ["Bash(ls)"]}, "theme": "dark"}), encoding="utf-8")
    assert sh(clone, "sh", "install.sh").returncode == 0
    data = settings(clone)
    assert data["permissions"]["deny"] == ["Bash(curl *)", "Read(/vault/people/*/private/**)"]
    assert data["permissions"]["allow"] == ["Bash(ls)"] and data["theme"] == "dark"


@pytest.mark.parametrize("content", ["{not json", "[]", '{"permissions": {"deny": "x"}}'])
def test_install_fails_loud_and_never_overwrites_a_malformed_settings(clone, content):
    path = clone / ".claude" / "settings.json"
    path.write_text(content, encoding="utf-8")
    r = sh(clone, "sh", "install.sh")
    assert r.returncode != 0 and "NOT completed" in r.stderr
    assert "Traceback" not in r.stderr and "ERROR:" in r.stderr  # a clean error, not a crash
    assert path.read_text(encoding="utf-8") == content


def test_install_fails_loud_on_a_bad_private_txt_line(clone):
    (clone / "vault" / "private.txt").write_text("../outside\n", encoding="utf-8")
    r = sh(clone, "sh", "install.sh")
    assert r.returncode != 0 and "private.txt:1" in r.stderr


def test_check_goes_red_when_a_rule_is_missing(clone):
    assert sh(clone, "python3", str(SCRIPT), "--check").returncode == 0
    (clone / "vault" / "private.txt").write_text("people/*/private/**\nextra/**\n", encoding="utf-8")
    r = sh(clone, "python3", str(SCRIPT), "--check")
    assert r.returncode == 1 and "Read(/vault/extra/**)" in r.stdout


def test_without_private_txt_install_writes_no_settings(clone):
    (clone / ".claude" / "settings.json").unlink()
    (clone / "vault" / "private.txt").unlink()
    assert sh(clone, "sh", "install.sh").returncode == 0
    assert not (clone / ".claude" / "settings.json").exists()
