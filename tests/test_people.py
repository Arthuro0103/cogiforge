"""people.py: team mode. Solo is inert; a member cannot touch another person's folder; an admin can."""
import subprocess
import sys
from pathlib import Path

import pytest

import people
import ring
from helpers import vault
from test_hook_e2e import clone, commit, sh  # noqa: F401  (fixture)

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "people.py"
ROLES = people.parse_roles("ana admin ana@example.com\nbia member bia@example.com\n")


def findings(email, *changes):
    return people.judge(ROLES, email, [(st, f"vault/{p}") for st, p in changes])


# ---- unit: the four checks, each as a positive/negative pair --------------------

def test_member_in_their_own_folder_passes():
    assert findings("bia@example.com", ("M", "people/bia/memory/profile.md")) == []


def test_member_in_another_folder_is_blocked():
    out = findings("bia@example.com", ("M", "people/ana/memory/profile.md"))
    assert len(out) == 1 and "people/ana/" in out[0]


def test_member_deleting_in_another_folder_is_blocked():
    assert findings("bia@example.com", ("D", "people/ana/x.md"))


def test_member_in_the_template_is_blocked_but_admin_passes():
    assert findings("bia@example.com", ("M", "people/_template/memory/profile.md"))
    assert findings("ana@example.com", ("M", "people/_template/memory/profile.md")) == []


@pytest.mark.parametrize("name", ["roles.txt", "areas.txt"])
def test_member_on_admin_files_is_blocked_and_admin_passes(name):
    assert findings("bia@example.com", ("M", name))
    assert findings("ana@example.com", ("M", name)) == []


def test_member_creating_a_project_is_blocked_but_editing_one_passes():
    assert findings("bia@example.com", ("A", "projects/new/instructions.md"))
    assert findings("bia@example.com", ("M", "projects/old/instructions.md")) == []
    assert findings("bia@example.com", ("A", "projects/new/other.md")) == []


def test_member_creating_a_note_passes():
    assert findings("bia@example.com", ("A", "notes/learning/x.md")) == []


def test_admin_passes_everything():
    assert findings("ana@example.com", ("M", "people/bia/x.md"), ("A", "projects/n/instructions.md"),
                    ("M", "roles.txt")) == []


def test_unknown_author_is_blocked_and_told_how_to_join():
    out = findings("eve@example.com", ("A", "notes/learning/x.md"))
    assert out and "ask an admin" in out[0]
    assert findings("", ("A", "notes/learning/x.md"))


def test_email_match_ignores_case():
    assert findings("bia@example.com".upper(), ("A", "notes/learning/x.md")) == []


def test_paths_outside_the_vault_are_not_judged():
    assert people.judge(ROLES, "bia@example.com", [("M", "docs/people/ana/x.md")]) == []


def test_bad_roles_line_raises_instead_of_guessing():
    for bad in ("ana admin", "ana boss ana@example.com", "ana admin not-an-email"):
        with pytest.raises(people.RolesError):
            people.parse_roles(bad)


def test_comments_and_blank_lines_are_ignored():
    assert people.parse_roles("# c\n\nana admin ana@example.com  # boss\n") == {"ana@example.com": ("ana", "admin")}


# ---- run(): solo, and a check that touched nothing is not OK -----------------------

def test_solo_mode_is_silent_rc_0(tmp_path, capsys):
    assert people.run(vault(tmp_path, {"home.md": "x\n"}), [("M", "vault/people/ana/x.md")], "") == 0
    assert capsys.readouterr().out == ""


def test_team_mode_blocks_and_passes(tmp_path):
    v = vault(tmp_path, {"roles.txt": "ana admin ana@example.com\nbia member bia@example.com\n"})
    assert people.run(v, [("M", "vault/people/ana/x.md")], "bia@example.com") == 1
    assert people.run(v, [("M", "vault/notes/x.md")], "bia@example.com") == 0


def test_empty_roles_is_not_verified_never_ok(tmp_path, capsys):
    v = vault(tmp_path, {"roles.txt": "# nobody\n"})
    assert people.run(v, [("M", "vault/notes/x.md")], "a@example.com") == 3
    assert "NOT_VERIFIED" in capsys.readouterr().out


def test_unreadable_roles_is_not_verified(tmp_path, capsys):
    v = vault(tmp_path, {"roles.txt": "ana admin ana@example.com\n"})
    (v / "roles.txt").write_bytes(b"\xff\xfe\x00bad")
    assert people.run(v, [("M", "vault/notes/x.md")], "ana@example.com") == 3  # not read: never OK
    assert "NOT_VERIFIED" in capsys.readouterr().out


def test_bad_line_is_rc_2(tmp_path):
    v = vault(tmp_path, {"roles.txt": "ana admin\n"})
    assert people.run(v, [], "a@example.com") == 2


def test_output_has_file_and_reason_only(tmp_path, capsys):
    v = vault(tmp_path, {"roles.txt": "ana admin ana@example.com\nbia member bia@example.com\n"})
    people.run(v, [("M", "vault/people/ana/memory/profile.md")], "bia@example.com")
    assert "people/ana/memory/profile.md" in capsys.readouterr().out


def test_selftest_runs_green():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "SELFTEST OK" in r.stdout


# ---- ring: each person's inbox is exempt like the vault's ------------------------------

def test_people_inbox_orphan_is_exempt():
    assert ring.is_deposit("people/ana/inbox/idea.md")
    assert not ring.is_deposit("people/ana/memory/profile.md")
    assert not ring.is_deposit("people/ana/inbox-not/x.md")
    assert not ring.is_deposit("notes/people/ana/inbox/x.md")


def test_people_inbox_orphan_does_not_fail_the_ring(tmp_path):
    base = {"a.md": "[[b]]\n", "b.md": "[[a]]\n"}
    v = vault(tmp_path, {**base, "people/ana/inbox/idea.md": "loose\n"})
    notes, deg = ring.analyze(v)
    assert ring.chk_orphans(notes, deg) == []
    v2 = vault(tmp_path / "2", {**base, "people/ana/notes/idea.md": "loose\n"})
    notes, deg = ring.analyze(v2)
    assert ring.chk_orphans(notes, deg) == ["people/ana/notes/idea.md"]


# ---- end to end: the real hook, in a temporary clone -----------------------------------------

def team(repo, handle="ana", email="ana@example.com"):
    sh(repo, "git", "config", "user.email", email)
    r = sh(repo, "sh", "install.sh", "--team", handle)
    assert r.returncode == 0, r.stdout + r.stderr
    sh(repo, "git", "add", "-A")
    r = sh(repo, "git", "commit", "-q", "-m", "team")
    assert r.returncode == 0, r.stdout + r.stderr


def as_member(repo, handle="bia", email="bia@example.com"):
    roles = repo / "vault" / "roles.txt"
    roles.write_text(roles.read_text(encoding="utf-8") + f"{handle} member {email}\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    assert sh(repo, "git", "commit", "-q", "-m", "add member").returncode == 0  # still the admin's e-mail
    sh(repo, "git", "config", "user.email", email)


NOTE = "---\ntype: note\narea: learning\n---\n# A member note\n\nBack to [[home]].\n"


def test_install_team_creates_roles_and_the_folder(clone):
    team(clone)
    assert "ana admin ana@example.com" in (clone / "vault/roles.txt").read_text(encoding="utf-8")
    assert (clone / "vault/people/ana/memory/profile.md").is_file()
    assert (clone / "vault/people/ana/inbox/.gitkeep").is_file()


def test_install_team_twice_refuses_to_overwrite(clone):
    team(clone)
    r = sh(clone, "sh", "install.sh", "--team", "zed")
    assert r.returncode != 0 and "roles.txt" in r.stdout + r.stderr


@pytest.mark.parametrize("handle", ["Ana", "_x", "a b", ""])
def test_install_team_rejects_a_bad_handle(clone, handle):
    r = sh(clone, "sh", "install.sh", "--team", handle)
    assert r.returncode != 0 and not (clone / "vault/roles.txt").exists()


def test_install_without_flag_does_not_enter_team_mode(clone):
    assert not (clone / "vault/roles.txt").exists()


def test_install_rejects_an_unknown_flag(clone):
    assert sh(clone, "sh", "install.sh", "--nope").returncode != 0


def test_member_in_another_folder_blocks_the_commit(clone):
    team(clone)
    as_member(clone)
    r = commit(clone, "vault/people/ana/memory/extra.md", "# x\n\n[[home]]\n")
    assert r.returncode == 1 and "COMMIT BLOCKED" in r.stdout + r.stderr and "people/ana/" in r.stdout + r.stderr


def test_member_note_in_notes_passes(clone):
    team(clone)
    as_member(clone)
    r = commit(clone, "vault/notes/learning/member-note.md", NOTE)
    assert r.returncode == 0, r.stdout + r.stderr


def test_member_in_their_own_folder_passes(clone):
    team(clone)
    as_member(clone)
    sh(clone, "cp", "-R", "vault/people/_template", "vault/people/bia")
    sh(clone, "git", "add", "vault/people/bia")
    r = sh(clone, "git", "commit", "-q", "-m", "own folder")
    assert r.returncode == 0, r.stdout + r.stderr


def test_member_editing_roles_is_blocked(clone):
    team(clone)
    as_member(clone)
    roles = clone / "vault/roles.txt"
    r = commit(clone, "vault/roles.txt", roles.read_text(encoding="utf-8") + "eve admin eve@example.com\n")
    assert r.returncode == 1 and "roles.txt" in r.stdout + r.stderr


def test_unknown_author_is_blocked_by_the_hook(clone):
    team(clone)
    sh(clone, "git", "config", "user.email", "eve@example.com")
    r = commit(clone, "vault/notes/learning/x.md", NOTE)
    assert r.returncode == 1 and "ask an admin" in r.stdout + r.stderr


def test_admin_can_touch_another_persons_folder(clone):
    team(clone)
    r = commit(clone, "vault/people/other/memory/x.md", "# x\n\n[[home]]\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_removing_roles_goes_back_to_solo(clone):
    team(clone)
    as_member(clone)
    (clone / "vault/roles.txt").unlink()
    r = commit(clone, "vault/people/ana/memory/extra.md", "# x\n\n[[home]]\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_roles_with_the_emails_does_not_trip_the_leak_scanner(clone):
    team(clone)  # the commit inside `team` already carried vault/roles.txt
    assert "ana@example.com" in (clone / "vault/roles.txt").read_text(encoding="utf-8")


# ---- tests that kill the mutants a first round left alive ---------------------------------

def test_roles_are_stored_case_insensitive():
    assert "bia@example.com" in people.parse_roles("bia member BIA@example.com\n")


def test_staged_deletions_are_seen_by_the_stage_reader(tmp_path, monkeypatch):
    sh(tmp_path, "git", "init", "-q")
    sh(tmp_path, "git", "config", "user.email", "t@example.com")
    sh(tmp_path, "git", "config", "user.name", "t")
    (tmp_path / "a.md").write_text("x\n", encoding="utf-8")
    sh(tmp_path, "git", "add", "a.md")
    sh(tmp_path, "git", "commit", "-q", "-m", "a")
    sh(tmp_path, "git", "rm", "-q", "a.md")
    monkeypatch.chdir(tmp_path)
    assert people.staged_changes() == [("D", "a.md")]


def test_a_path_that_only_looks_like_the_vault_prefix_is_not_judged():
    # "other/" has the same length as "vault/": cutting by length alone would turn this into people/ana/x.md
    assert people.judge(ROLES, "bia@example.com", [("M", "other/people/ana/x.md")]) == []


def test_team_mode_without_a_readable_stage_is_rc_2_not_solo(tmp_path):
    vault(tmp_path, {"vault/roles.txt": "ana admin ana@example.com\n"})
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", "vault", "--staged"], cwd=tmp_path,
                       capture_output=True, text=True, env={"PATH": "/nonexistent", "HOME": str(tmp_path)})
    assert r.returncode == 2 and "nothing was judged" in r.stderr


def test_selftest_fails_when_a_check_is_broken(monkeypatch, capsys):
    monkeypatch.setattr(people, "CHECKS", ())
    assert people.selftest() == 1
    assert "SELFTEST FAILED" in capsys.readouterr().out


def test_roles_with_a_real_looking_email_is_exempt_from_the_leak_scan(clone):
    REAL = "ana@acme-corp" + ".io"  # assembled here so this file does not accuse itself
    team(clone, email=REAL)  # the commit inside `team` carries vault/roles.txt
    assert REAL in (clone / "vault/roles.txt").read_text(encoding="utf-8")
    assert "vault/roles.txt" in (clone / ".leakignore").read_text(encoding="utf-8")


def test_unreadable_team_mode_blocks_the_commit(clone):
    team(clone)
    (clone / "vault/roles.txt").write_text("# nobody\n", encoding="utf-8")
    r = commit(clone, "vault/notes/learning/x.md", NOTE)
    assert r.returncode == 1 and "could not be verified" in r.stdout + r.stderr
