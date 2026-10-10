"""conflicts.py: each sync pattern is found, the legitimate look-alikes are not, and the hook blocks."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import conflicts
from helpers import vault
from test_hook_e2e import clone, commit, sh  # noqa: F401  (fixture)

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "conflicts.py"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd)


def reasons(tmp_path, files):
    vault(tmp_path, {f: "x" for f in files})
    found, unreadable = conflicts.scan_disk([str(tmp_path)])
    assert unreadable == []
    return {Path(f).name: r for f, r in found}


@pytest.mark.parametrize("name,reason", [
    ("a (conflicted copy 2026-01-01).md", "conflicted-copy"),
    ("a (Ana's conflicted copy 2026-01-01).md", "conflicted-copy"),
    ("a (Case Conflict).md", "case-conflict"),
    ("a.sync-conflict-20260101-120000-ABCDEFG.md", "syncthing-conflict"),
    (".a.md.icloud", "icloud-placeholder"),
])
def test_each_pattern_is_found_alone(tmp_path, name, reason):
    assert reasons(tmp_path, [name]) == {name: reason}


def test_numbered_duplicate_with_sibling_is_found(tmp_path):
    got = reasons(tmp_path, ["x.md", "x (1).md", "y.md", "y 2.md"])
    assert got == {"x (1).md": "numbered-duplicate", "y 2.md": "numbered-duplicate"}


def test_legitimate_numbered_name_without_sibling_is_not_found(tmp_path):
    assert reasons(tmp_path, ["Chapter 2.md", "Plan (3).md", "Chapter 10.md"]) == {}


def test_sibling_must_be_in_the_same_folder(tmp_path):
    assert reasons(tmp_path, ["one/x.md", "two/x 2.md"]) == {}


def test_sibling_must_have_the_same_extension(tmp_path):
    assert reasons(tmp_path, ["x.md", "x 2.txt"]) == {}


def test_normal_notes_are_clean(tmp_path):
    assert reasons(tmp_path, ["note.md", "other note.md", "2026 plan.md"]) == {}


def test_cli_rcs(tmp_path):
    vault(tmp_path, {"v/a.md": "x"})
    assert run(str(tmp_path / "v")).returncode == 0
    vault(tmp_path, {"v/a (1).md": "x"})
    r = run(str(tmp_path / "v"))
    assert r.returncode == 1 and "a (1).md:numbered-duplicate" in r.stdout
    assert run(str(tmp_path / "missing")).returncode == 2
    assert run("--bogus").returncode == 2


def test_json_output(tmp_path):
    vault(tmp_path, {"v/a.md": "x", "v/a (1).md": "x"})
    r = run("--json", str(tmp_path / "v"))
    assert r.returncode == 1
    assert json.loads(r.stdout)[0]["reason"] == "numbered-duplicate"


def test_output_never_carries_content(tmp_path):
    vault(tmp_path, {"v/a.md": "x", "v/a (1).md": "SECRET-CONTENT"})
    assert "SECRET-CONTENT" not in run(str(tmp_path / "v")).stdout


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs chmod to bite")
def test_unreadable_folder_is_rc_3_never_clean(tmp_path):
    vault(tmp_path, {"v/locked/a.md": "x"})
    locked = tmp_path / "v" / "locked"
    locked.chmod(0)
    try:
        r = run(str(tmp_path / "v"))
    finally:
        locked.chmod(0o755)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_selftest_passes():
    assert run("--selftest").returncode == 0


# ---- staged: only what the commit carries --------------------------------------

def git(cwd, *cmd):
    return subprocess.run(["git", *cmd], cwd=cwd, capture_output=True, text=True)


def test_staged_only_looks_at_the_commit(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    vault(tmp_path, {"a.md": "x", "a (1).md": "x"})
    git(tmp_path, "add", "a.md")
    assert run("--staged", cwd=tmp_path).returncode == 0  # the duplicate is on disk, not in the commit
    git(tmp_path, "add", "a (1).md")
    r = run("--staged", cwd=tmp_path)
    assert r.returncode == 1 and "a (1).md:numbered-duplicate" in r.stdout
    git(tmp_path, "commit", "-q", "-m", "x", "--no-verify")
    assert run("--staged", cwd=tmp_path).returncode == 0  # already committed: nothing staged


def test_staged_without_git_is_rc_2(tmp_path):
    assert run("--staged", cwd=tmp_path).returncode == 2


# ---- the hook, end to end ------------------------------------------------------

def test_hook_blocks_a_duplicate_and_teaches(clone):
    commit(clone, "vault/notes/life/x.md", "---\narea: life\n---\n# X\n\nBack to [[home]].\n")
    r = commit(clone, "vault/notes/life/x (1).md", "---\narea: life\n---\n# X\n\nBack to [[home]].\n")
    out = r.stdout + r.stderr
    assert r.returncode == 1 and "COMMIT BLOCKED" in out and "How to fix" in out and "x (1).md" in out


def test_hook_tells_the_user_what_to_do_with_the_duplicate(clone):
    commit(clone, "vault/notes/life/x.md", "---\narea: life\n---\n# X\n\nBack to [[home]].\n")
    r = commit(clone, "vault/notes/life/x (1).md", "---\narea: life\n---\n# X\n\nBack to [[home]].\n")
    out = r.stdout + r.stderr
    assert r.returncode == 1 and "How to fix: compare the copy with the original" in out and "docs/SYNC.md" in out


def test_hook_lets_a_normal_note_pass(clone):
    r = commit(clone, "vault/notes/life/Chapter 2.md", "---\narea: life\n---\n# C\n\nBack to [[home]].\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_hook_no_verify_still_escapes(clone):
    commit(clone, "vault/notes/life/x.md", "---\narea: life\n---\n# X\n\nBack to [[home]].\n")
    r = commit(clone, "vault/notes/life/x (1).md", "---\narea: life\n---\n# X\n\n[[home]]\n", "--no-verify")
    assert r.returncode == 0


def test_hook_without_conflicts_py_is_an_incomplete_installation(clone):
    (clone / "core" / "conflicts.py").unlink()
    r = commit(clone, "vault/notes/life/n.md", "---\narea: life\n---\n# N\n\nBack to [[home]].\n")
    assert r.returncode == 1 and "installation is incomplete" in r.stdout + r.stderr
