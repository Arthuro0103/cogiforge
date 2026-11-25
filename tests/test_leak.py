"""leak.py: every check gets a pair (input that leaks + plausible input that passes).

Leaky strings are assembled at runtime so this file itself never trips the scanner.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import leak as v

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "core" / "leak.py"

PATH = "/Users/" + "jdoe"
EMAIL = "jdoe" + "@" + "company.com.br"
CPF = "123.456.789-" + "09"
PHONE_PAREN = "(11) 9" + "8765-4321"
PHONE_PLUS = "+55 21 9" + "8765-4321"
PHONE_BARE = "11 9" + "8765-4321"


# ---- pairs: leaks / passes ---------------------------------------------------

@pytest.mark.parametrize("line", [f"open {PATH}/docs/x.md", f"cd {PATH}"])
def test_path_leaks(line):
    assert v.chk_path(line)


@pytest.mark.parametrize("line", [
    "the macOS /Users folder", "see ~/www/project", "/Users/<name>/docs", "/usr/local/bin",
])
def test_plausible_path_passes(line):
    assert v.chk_path(line) == []


def test_email_leaks():
    assert v.chk_email(f"talk to {EMAIL} today")


@pytest.mark.parametrize("line", [
    "write to jdoe@example.com", "git clone git@github.com:org/repo.git",
    "use @mention in the text", "price 10@5 dollars",
])
def test_plausible_email_passes(line):
    assert v.chk_email(line) == []


@pytest.mark.parametrize("line", [f"call {PHONE_PAREN}", f"chat {PHONE_PLUS}", f"tel {PHONE_BARE}"])
def test_phone_leaks(line):
    assert v.chk_phone(line)


@pytest.mark.parametrize("line", [
    "timestamp 1759500000", "date 2026-10-03", "python 3.10-3.13", "version 1234-5678 of the manual",
])
def test_plausible_phone_passes(line):
    assert v.chk_phone(line) == []


def test_cpf_leaks():
    assert v.chk_cpf(f"cpf {CPF}")


@pytest.mark.parametrize("line", ["12345678909", "1.2.3", "ip 192.168.100.200-1"])
def test_plausible_cpf_passes(line):
    assert v.chk_cpf(line) == []


def test_list_leaks_regardless_of_case():
    assert v.chk_list("the Project Zeta-Quux is here", ["zeta-quux"])
    assert v.chk_list("ZETA-QUUX", ["zeta-quux"])


def test_plausible_list_passes():
    assert v.chk_list("nothing special here", ["zeta-quux", "other term"]) == []
    assert v.chk_list("anything", []) == []


# ---- blocklist: reading, absence, file outside -------------------------------

def test_read_blocklist_ignores_empty_lines_and_comments(tmp_path):
    f = tmp_path / "blocklist.txt"
    f.write_text("# comment\nzeta-quux\n\n  Other Term  \n", encoding="utf-8")
    assert v.read_blocklist(f) == ["zeta-quux", "other term"]


def test_read_blocklist_missing_returns_none(tmp_path):
    assert v.read_blocklist(tmp_path / "does-not-exist.txt") is None


# ---- end-to-end scan (a real process) ---------------------------------------

def run(args, cwd, blocklist=None, env=None):
    base = {"PATH": "/usr/bin:/bin:/usr/local/bin", "LEAK_BLOCKLIST": str(blocklist or cwd / "absent.txt")}
    if env is not None:  # explicit env: replaces the default one (so a test can leave LEAK_BLOCKLIST unset)
        base = {"PATH": "/usr/bin:/bin:/usr/local/bin", **env}
    if sys.platform == "win32":  # a replaced env still needs the Windows basics; Path.home() reads USERPROFILE, not HOME
        base["PATH"] = os.environ["PATH"]  # git (called by leak.py) is not under /usr/bin here
        base.setdefault("SYSTEMROOT", os.environ.get("SYSTEMROOT", ""))
        base.setdefault("USERPROFILE", base.get("HOME", str(cwd)))
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=base,
                          capture_output=True, text=True)


def test_scan_finds_and_counts_lines(tmp_path):
    (tmp_path / "bad.md").write_text(f"ok\nleaked {PATH}/x\nok\nmail {EMAIL}\n", encoding="utf-8")
    (tmp_path / "good.md").write_text("clean text\nnothing\n", encoding="utf-8")
    r = run(["."], tmp_path)
    found = [l for l in r.stdout.splitlines() if l.startswith("bad.md:")]
    assert r.returncode == 1
    assert len(found) == 2 and "good.md" not in r.stdout


def test_clean_scan_exits_zero(tmp_path):
    (tmp_path / "good.md").write_text("clean text\n", encoding="utf-8")
    assert run(["."], tmp_path).returncode == 0


def test_without_a_private_list_says_not_verified_and_never_ok(tmp_path):
    (tmp_path / "good.md").write_text("clean text\n", encoding="utf-8")
    r = run(["."], tmp_path)
    assert "NOT_VERIFIED" in r.stdout
    assert "OK" not in r.stdout.replace("NOT_VERIFIED", "")


def test_require_list_without_a_list_exits_3(tmp_path):
    (tmp_path / "good.md").write_text("clean text\n", encoding="utf-8")
    assert run([".", "--require-list"], tmp_path).returncode == 3


def test_with_a_private_list_finds_the_term(tmp_path):
    blocklist = tmp_path / "outside" / "blocklist.txt"
    blocklist.parent.mkdir()
    blocklist.write_text("zeta-quux\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("talks about Zeta-Quux here\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, blocklist=blocklist)
    assert r.returncode == 1 and "blocklist" in r.stdout
    assert "NOT_VERIFIED: private blocklist" not in r.stdout  # the git-index line outside a repo is a separate check


@pytest.mark.parametrize("name", ["blocklist.txt", "negra.txt"])
def test_file_named_like_the_private_list_is_ignored(tmp_path, name):
    (tmp_path / name).write_text(f"{EMAIL}\n{PATH}\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / name).write_text(EMAIL + "\n", encoding="utf-8")
    assert run(["."], tmp_path).returncode == 0


@pytest.mark.parametrize("name", ["blocklist.txt", "negra.txt"])
def test_file_named_like_the_private_list_passed_directly_is_also_ignored(tmp_path, name):
    (tmp_path / name).write_text(EMAIL + "\n", encoding="utf-8")
    assert run([name], tmp_path).returncode == 0


def test_ignore_file_and_no_ignore(tmp_path):
    (tmp_path / "planted.md").write_text(f"leaks {PATH}\n", encoding="utf-8")
    (tmp_path / ".leakignore").write_text("# fixture\nplanted.md\n", encoding="utf-8")
    assert run(["."], tmp_path).returncode == 0
    assert run([".", "--no-ignore"], tmp_path).returncode == 1


def test_binary_and_git_are_skipped(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(EMAIL, encoding="utf-8")
    (tmp_path / "img.bin").write_bytes(b"\xff\xfe\x00" + EMAIL.encode())
    r = run(["."], tmp_path)
    # the fake `.git` folder is not a readable repo (rc 2, NOT_VERIFIED), but nothing inside it was scanned
    assert r.returncode in (0, 2) and "0 finding(s)" in r.stdout


def test_output_does_not_echo_the_data(tmp_path):
    (tmp_path / "x.md").write_text(f"{EMAIL} {PATH}\n", encoding="utf-8")
    r = run(["."], tmp_path)
    assert "jdoe" not in r.stdout


def test_dot_git_worktree_file_is_skipped(tmp_path):
    (tmp_path / ".git").write_text(f"gitdir: {PATH}/repo/.git/worktrees/x\n", encoding="utf-8")
    assert run(["."], tmp_path).returncode == 0
    assert run([".git"], tmp_path).returncode == 0


def _no_git_above(path):
    return not any((a / ".git").exists() for a in [path, *path.parents])


def test_folder_outside_any_repo_is_not_verified_rc0(tmp_path):
    if not _no_git_above(tmp_path):
        pytest.skip("tmp_path has a .git in an ancestor")
    (tmp_path / "x.md").write_text("clean\n", encoding="utf-8")
    r = run(["."], tmp_path)
    assert r.returncode == 0 and "not inside a git repo" in r.stdout


@pytest.mark.parametrize("kind", ["empty", "junk_head"])
def test_broken_dot_git_folder_is_rc2(tmp_path, kind):
    (tmp_path / ".git").mkdir()
    if kind == "junk_head":
        (tmp_path / ".git" / "HEAD").write_text("garbage\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("clean\n", encoding="utf-8")
    r = run(["."], tmp_path)
    assert r.returncode == 2 and "git rev-parse failed" in r.stdout


def test_dot_git_link_to_existing_non_repo_is_rc2(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / ".git").write_text(f"gitdir: {tmp_path / 'target'}\n", encoding="utf-8")
    r = run(["."], tmp_path / "work")
    assert r.returncode == 2 and "git rev-parse failed" in r.stdout


# ---- fail-open and normalization (security review of the commit) -------------

def test_invalid_utf8_does_not_hide_a_leak(tmp_path):
    (tmp_path / "x.md").write_bytes(b"\xe9\xff junk\nmail " + EMAIL.encode() + b"\n")
    r = run(["."], tmp_path)
    assert r.returncode == 1 and "x.md:2: email" in r.stdout


def test_utf16_with_bom_is_read(tmp_path):
    (tmp_path / "x.md").write_bytes(("mail " + EMAIL + "\n").encode("utf-16"))
    assert run(["."], tmp_path).returncode == 1


@pytest.mark.skipif(sys.platform == "win32", reason="chmod(0) cannot make a file unreadable on Windows (POSIX permission bits)")
def test_unreadable_file_is_not_verified_and_never_clean(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("clean\n", encoding="utf-8")
    f.chmod(0)
    try:
        r = run(["."], tmp_path)
    finally:
        f.chmod(0o644)
    assert r.returncode == 2 and "NOT_VERIFIED" in r.stdout and "x.md" in r.stdout


@pytest.mark.parametrize("line", [
    "zeta\u200b-quux", "ZETA\u00ad-QUUX", "ｚｅｔａ-ｑｕｕｘ", "zeta\ufeff-quux",
])
def test_list_resists_zero_width_and_full_width(line):
    assert v.chk_list(v.normalize(line), ["zeta-quux"])


def test_email_and_path_resist_full_width():
    full = lambda t: "".join(chr(ord(c) + 0xFEE0) if c != " " else c for c in t)  # ASCII -> full width
    assert v.chk_email(v.normalize("jdoe" + full("@") + "company.com.br"))
    assert v.chk_path(v.normalize(full("/Users/") + "jdoe"))


@pytest.mark.parametrize("line", ["/users/" + "jdoe", "C:\\Users\\" + "jdoe\\x", "/USERS/" + "jdoe"])
def test_path_case_and_windows(line):
    assert v.chk_path(line)


def test_zero_width_in_the_end_to_end_scan(tmp_path):
    blocklist = tmp_path / "outside" / "blocklist.txt"
    blocklist.parent.mkdir()
    blocklist.write_text("zeta-quux\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("talks about zeta\u200b-quux here\n", encoding="utf-8")
    assert run(["x.md"], tmp_path, blocklist=blocklist).returncode == 1


@pytest.mark.parametrize("name", ["blocklist.txt", "negra.txt"])
def test_private_list_in_the_stage_blocks_the_commit(tmp_path, name):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True)
    git("init", "-q")
    (tmp_path / name).write_text("term\n", encoding="utf-8")
    assert git("add", "-f", name).returncode == 0
    r = run(["--staged"], tmp_path)
    assert r.returncode == 1 and "blocklist-staged" in r.stdout


def _git_repo(tmp_path, tracked_file):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True)
    git("init", "-q")
    target = tmp_path / ".claude" / "settings.local.json"
    target.parent.mkdir()
    target.write_text('{"permissions": {"allow": ["Bash(echo hi)"]}}\n', encoding="utf-8")
    if tracked_file:
        assert git("add", "-f", ".claude/settings.local.json").returncode == 0
    else:
        (tmp_path / ".gitignore").write_text(".claude/settings.local.json\n", encoding="utf-8")
        assert git("add", ".gitignore").returncode == 0
    return git


def test_tracked_settings_local_json_fails(tmp_path):
    _git_repo(tmp_path, tracked_file=True)
    r = run([], tmp_path)
    assert r.returncode == 1 and "settings-local-tracked" in r.stdout and "git rm --cached" in r.stdout


def test_staged_settings_local_json_fails(tmp_path):
    _git_repo(tmp_path, tracked_file=True)
    r = run(["--staged"], tmp_path)
    assert r.returncode == 1 and "settings-local-tracked" in r.stdout


def test_tracked_settings_local_json_not_exempted_by_leakignore(tmp_path):
    _git_repo(tmp_path, tracked_file=True)
    (tmp_path / ".leakignore").write_text(".claude/settings.local.json\n", encoding="utf-8")
    assert run([], tmp_path).returncode == 1


def test_ignored_settings_local_json_passes(tmp_path):
    _git_repo(tmp_path, tracked_file=False)
    r = run([], tmp_path)
    assert r.returncode == 0 and "settings-local-tracked" not in r.stdout


def _commit_settings_local(tmp_path, rel):
    """Repo with `rel` committed (git identity set locally, no global config needed)."""
    def git(*a):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                              cwd=tmp_path, capture_output=True, text=True)
    git("init", "-q")
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    assert git("add", "-f", rel).returncode == 0
    assert git("commit", "-qm", "x").returncode == 0
    return git


def test_settings_local_json_in_a_subfolder_fails(tmp_path):
    # "any folder of the repo": a root-only match would let this one through
    _commit_settings_local(tmp_path, "sub dir/ção/.claude/settings.local.json")
    r = run([], tmp_path)
    assert r.returncode == 1 and "settings-local-tracked" in r.stdout
    assert "'" in r.stdout.split("git rm --cached", 1)[1].split("\n", 1)[0]  # path with a space is quoted


def test_settings_local_json_deleted_from_disk_but_in_the_index_fails(tmp_path):
    _commit_settings_local(tmp_path, ".claude/settings.local.json")
    (tmp_path / ".claude" / "settings.local.json").unlink()  # still committed by the next `git commit`
    assert run([], tmp_path).returncode == 1
    assert run(["--staged"], tmp_path).returncode == 1


def test_staged_mode_flags_a_settings_local_json_committed_before(tmp_path):
    # the pre-commit hook runs --staged: an old commit must not hide it just because it did not change
    git = _commit_settings_local(tmp_path, ".claude/settings.local.json")
    (tmp_path / "a.txt").write_text("hi\n", encoding="utf-8")
    assert git("add", "a.txt").returncode == 0
    r = run(["--staged"], tmp_path)
    assert r.returncode == 1 and "settings-local-tracked" in r.stdout


def test_settings_local_json_found_when_run_from_inside_a_subfolder(tmp_path):
    _commit_settings_local(tmp_path, ".claude/settings.local.json")
    assert run([], tmp_path / ".claude").returncode == 1


def test_settings_local_json_with_other_case_fails(tmp_path):
    _commit_settings_local(tmp_path, ".Claude/Settings.Local.json")
    assert run([], tmp_path).returncode == 1


def test_the_suggested_gitignore_line_covers_subfolders(tmp_path):
    git = _commit_settings_local(tmp_path, "keep.txt")
    (tmp_path / ".gitignore").write_text(v.SETTINGS_LOCAL_IGNORE + "\n", encoding="utf-8")
    sub = tmp_path / "sub" / ".claude"
    sub.mkdir(parents=True)
    (sub / "settings.local.json").write_text("{}\n", encoding="utf-8")
    r = git("-c", "core.excludesFile=/dev/null", "check-ignore", "-q", "sub/.claude/settings.local.json")
    assert r.returncode == 0


# ---- allowlists and fail-open (2nd security review) --------------------------

def test_example_exemption_does_not_cover_a_real_domain_that_starts_with_example():
    assert v.chk_email("jdoe" + "@" + "example.com.br")
    assert v.chk_email("jdoe" + "@" + "example.com-corp.io")
    assert v.chk_email("write to jdoe@example.com.") == []
    assert v.chk_email("list: a@example.com, b@example.org;") == []


def test_email_followed_by_a_colon_still_leaks_but_git_scp_does_not():
    assert v.chk_email("contact " + EMAIL + ": phone below")
    assert v.chk_email("git clone git@github.com:org/repo.git") == []
    assert v.chk_email("ssh@server.dev:/srv") == []


def test_empty_or_comment_only_blocklist_is_not_verified(tmp_path):
    (tmp_path / "good.md").write_text("clean\n", encoding="utf-8")
    for content in ("", "\n\n", "# only a comment\n"):
        blocklist = tmp_path / "empty.txt"
        blocklist.write_text(content, encoding="utf-8")
        r = run([".", "--require-list"], tmp_path, blocklist=blocklist)
        assert "NOT_VERIFIED" in r.stdout and r.returncode == 3, content


def test_blocklist_with_an_invalid_byte_neither_crashes_nor_vanishes(tmp_path):
    blocklist = tmp_path / "outside.txt"
    blocklist.write_bytes(b"zeta-quux\n\xff\xfe broken\n")
    (tmp_path / "x.md").write_text("zeta-quux\n", encoding="utf-8")
    assert run(["x.md"], tmp_path, blocklist=blocklist).returncode == 1


def test_missing_path_is_not_clean(tmp_path):
    r = run(["does-not-exist"], tmp_path)
    assert r.returncode == 2 and "does-not-exist" in (r.stdout + r.stderr)


def test_venv_and_node_modules_folders_are_not_exempt(tmp_path):
    for d in ("venv", "node_modules", "sub/venv"):
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "x.md").write_text(EMAIL + "\n", encoding="utf-8")
    r = run(["."], tmp_path)
    assert r.returncode == 1 and len([l for l in r.stdout.splitlines() if ": email" in l]) == 3


@pytest.mark.parametrize("name", ["blocklist.txt", "negra.txt"])
def test_versioned_private_list_is_a_finding_in_a_repo_scan(tmp_path, name):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True)
    git("init", "-q")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / name).write_text("term\n", encoding="utf-8")
    (tmp_path / name).write_text("term\n", encoding="utf-8")
    git("add", "-f", f"docs/{name}")
    r = run(["."], tmp_path)
    assert r.returncode == 1 and f"docs/{name}:0: blocklist-in-repo" in r.stdout
    assert f"\n{name}:" not in "\n" + r.stdout  # the unversioned one is still ignored


def test_exemption_from_leakignore_shows_in_the_output(tmp_path):
    (tmp_path / "planted.md").write_text(f"leaks {PATH}\n", encoding="utf-8")
    (tmp_path / ".leakignore").write_text("planted.md\n", encoding="utf-8")
    r = run(["."], tmp_path)
    assert r.returncode == 0 and "exempt" in r.stdout and "planted.md" in r.stdout


def test_default_blocklist_lives_outside_the_repo_in_config_cogiforge():
    assert v.BLOCKLIST_DEFAULT == Path.home() / ".config" / "cogiforge" / "blocklist.txt"
    assert v.LEGACY_BLOCKLIST_DEFAULT == Path.home() / ".config" / "cogiforge" / "negra.txt"


# ---- rename fallback: blocklist.txt first, negra.txt with a WARNING ----------

def home_with(tmp_path, name, content):
    home = tmp_path / "home"
    (home / ".config" / "cogiforge").mkdir(parents=True, exist_ok=True)
    (home / ".config" / "cogiforge" / name).write_text(content, encoding="utf-8")
    return str(home)


def test_old_name_negra_txt_is_read_with_a_warning(tmp_path):
    home = home_with(tmp_path, "negra.txt", "zeta-quux\n")
    (tmp_path / "x.md").write_text("talks about zeta-quux here\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, env={"HOME": home})
    assert r.returncode == 1 and "x.md:1: blocklist" in r.stdout
    assert "WARNING" in r.stdout and "renamed" in r.stdout and "negra.txt" in r.stdout
    assert "NOT_VERIFIED: private blocklist" not in r.stdout  # the git-index line outside a repo is a separate check


def test_old_name_with_a_plausible_input_passes_but_still_warns(tmp_path):
    home = home_with(tmp_path, "negra.txt", "zeta-quux\n")
    (tmp_path / "x.md").write_text("nothing special here\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, env={"HOME": home})
    assert r.returncode == 0 and "WARNING" in r.stdout and "negra.txt" in r.stdout


def test_new_name_wins_over_the_old_one_without_a_warning(tmp_path):
    home = home_with(tmp_path, "negra.txt", "old-term\n")
    home_with(tmp_path, "blocklist.txt", "zeta-quux\n")
    (tmp_path / "x.md").write_text("old-term and zeta-quux\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, env={"HOME": home})
    assert r.returncode == 1 and "WARNING" not in r.stdout and "1 term(s)" in r.stdout


def test_neither_name_present_is_not_verified(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / "x.md").write_text("zeta-quux\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, env={"HOME": str(home)})
    assert r.returncode == 0 and "NOT_VERIFIED" in r.stdout and "WARNING" not in r.stdout


def test_old_env_var_is_accepted_with_a_warning(tmp_path):
    old = tmp_path / "list.txt"
    old.write_text("zeta-quux\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("zeta-quux\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, env={"VAZAMENTO_NEGRA": str(old)})
    assert r.returncode == 1 and "WARNING" in r.stdout and "LEAK_BLOCKLIST" in r.stdout


def test_new_env_var_wins_over_the_old_one(tmp_path):
    new, old = tmp_path / "new.txt", tmp_path / "old.txt"
    new.write_text("zeta-quux\n", encoding="utf-8")
    old.write_text("other\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("zeta-quux\n", encoding="utf-8")
    r = run(["x.md"], tmp_path, env={"LEAK_BLOCKLIST": str(new), "VAZAMENTO_NEGRA": str(old)})
    assert r.returncode == 1 and "WARNING" not in r.stdout


def test_leak_never_reads_gate_txt_and_blocks_whatever_it_says(tmp_path):
    """gate.txt only configures the orphan check. A leak is always a failure, and the scanner ignores the file."""
    assert "gate.txt" not in (Path(__file__).resolve().parent.parent / "core" / "leak.py").read_text(encoding="utf-8")
    for setting in ("orphan: warn\n", "orphan: block\n", "garbage\n", "leak: off\n"):
        (tmp_path / "gate.txt").write_text(setting, encoding="utf-8")
        (tmp_path / "x.txt").write_text("opened /Users/" + "jdoe/x\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "core" / "leak.py"), str(tmp_path)],
                           capture_output=True, text=True, env={**__import__("os").environ, "LEAK_BLOCKLIST": str(tmp_path / "none.txt")})
        assert r.returncode == 1, setting


# ---- the git index check: not looking is never "clean" ----------------------

def _init_repo(path, rel=None):
    path.mkdir(parents=True, exist_ok=True)

    def git(*a):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                              cwd=path, capture_output=True, text=True)
    git("init", "-q")
    if rel:
        t = path / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text("{}\n", encoding="utf-8")
        assert git("add", "-f", rel).returncode == 0
    return git


def test_unreadable_git_index_is_not_verified_and_never_clean(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hi\n", encoding="utf-8")
    (tmp_path / ".git" / "index").write_bytes(b"garbage")
    r = run([], tmp_path)
    assert r.returncode == 2, r.stdout
    assert "NOT_VERIFIED: could not read the git index" in r.stdout
    assert "settings.local.json may be missed" in r.stdout


def test_git_missing_from_path_is_not_verified(tmp_path):
    (tmp_path / "a.txt").write_text("hi\n", encoding="utf-8")
    r = run([], tmp_path, env={"LEAK_BLOCKLIST": str(tmp_path / "absent.txt"), "PATH": str(tmp_path / "nobin")})
    assert r.returncode == 2 and "NOT_VERIFIED: could not read the git index (git is not installed)" in r.stdout


def test_plain_folder_says_the_index_check_was_not_verified(tmp_path):
    (tmp_path / "a.txt").write_text("hi\n", encoding="utf-8")
    r = run([], tmp_path)
    assert "NOT_VERIFIED: could not read the git index (" in r.stdout and "not inside a git repo" in r.stdout


def test_scanning_repo_b_from_repo_a_finds_the_file_of_b(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _init_repo(a)
    _init_repo(b, ".claude/settings.local.json")
    r = run([str(b)], a)
    assert r.returncode == 1 and "settings-local-tracked" in r.stdout


def test_lookalike_folder_name_is_not_a_settings_local_finding(tmp_path):
    _init_repo(tmp_path, "foo.claude/settings.local.json")
    r = run([], tmp_path)
    assert "settings-local-tracked" not in r.stdout and r.returncode == 0
    assert not v.is_settings_local("foo.claude/settings.local.json")


def test_count_when_deleted_from_disk_but_in_the_index(tmp_path):
    _commit_settings_local(tmp_path, ".claude/settings.local.json")
    (tmp_path / ".claude" / "settings.local.json").unlink()
    r = run([], tmp_path)
    assert "1 finding(s) in 1 file(s), of 1 scanned" in r.stdout, r.stdout


def test_a_file_on_disk_and_in_the_index_counts_once(tmp_path):
    git = _commit_settings_local(tmp_path, ".claude/settings.local.json")
    (tmp_path / ".claude" / "settings.local.json").write_text("/" + "Users/someone/x\n", encoding="utf-8")
    r = run([], tmp_path)
    assert "in 1 file(s), of 1 scanned" in r.stdout, r.stdout
