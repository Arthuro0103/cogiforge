"""Paired tests for tools/adopt.py. ADOPT_PATH points to another copy (used by mutation).

Every test builds a small synthetic vault in tmp and runs the real command line.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADOPT = os.environ.get("ADOPT_PATH") or str(ROOT / "tools" / "adopt.py")


def build(base, files):
    for rel, content in files.items():
        p = Path(base) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return Path(base)


def adopt(vault, *args):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, ADOPT, str(vault), *args], capture_output=True, text=True,
                          env=env, stdin=subprocess.DEVNULL)


def git_init(vault):
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)


def local_cfg(vault, key):
    return subprocess.run(["git", "-C", str(vault), "config", "--local", "--get", key],
                          capture_output=True, text=True).stdout.strip()


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*")
            if p.is_file() and ".git/" not in p.as_posix()}


def load_module():
    spec = importlib.util.spec_from_file_location("adopt_tool", ADOPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 6 notes: Ideas/a <-> Ideas/b (b has a dead link), Work/c and Work/d orphans, Work/e -> [[a]], loose.md orphan
MINI = {
    "Ideas/a.md": "---\narea: ideas\n---\nsee [[b]]\n",
    "Ideas/b.md": "---\narea: ideas\n---\nback to [[a]] and [[ghost]]\n",
    "Work/c.md": "alone\n",
    "Work/d.md": "---\narea: work\n---\nalso alone\n",
    "Work/e.md": "---\narea: work\n---\npoints to [[a]]\n",
    "loose.md": "no link\n",
    ".obsidian/app.json": "{}",
    ".obsidian/notes.md": "# not a note of the user\n",
    "attachments/pic.png": b"\x89PNG",
}


def test_dry_run_writes_nothing(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    before = tree(tmp_path)
    r = adopt(tmp_path)
    assert "dry run" in r.stdout and "nothing is written" in r.stdout
    assert tree(tmp_path) == before
    assert not (tmp_path / ".githooks").exists() and not (tmp_path / ".cogiforge").exists()


def test_areas_ignore_obsidian_attachments_and_hidden(tmp_path):
    build(tmp_path, {**MINI, "attachments/x.md": "# x\n", ".hidden/h.md": "# h\n", "inbox/i.md": "# i\n"})
    plan = json.loads(adopt(tmp_path, "--json").stdout)
    assert sorted(plan["areas"]) == ["Ideas", "Work"]


def test_a_folder_without_notes_is_not_an_area(tmp_path):
    build(tmp_path, {"Photos/p.png": b"x", "Ideas/a.md": "# a\n"})
    assert list(json.loads(adopt(tmp_path, "--json").stdout)["areas"]) == ["Ideas"]


def test_debt_matches_the_planted_vault(tmp_path):
    build(tmp_path, MINI)
    d = json.loads(adopt(tmp_path, "--json").stdout)["debt"]
    # d.md is an orphan (nothing links to it, it links to nothing); c.md and loose.md too
    assert sorted(d["orphans"]) == ["Work/c.md", "Work/d.md", "loose.md"]
    assert d["area_missing"] == ["Work/c.md"]
    assert d["notes"] == 6 and len(d["dead_links"]) == 1 and "ghost" in d["dead_links"][0]


def test_a_clean_vault_has_no_debt(tmp_path):
    build(tmp_path, {"Ideas/a.md": "---\narea: ideas\n---\n[[b]]\n", "Ideas/b.md": "---\narea: ideas\n---\n[[a]]\n"})
    d = json.loads(adopt(tmp_path, "--json").stdout)["debt"]
    assert not d["orphans"] and not d["dead_links"] and not d["area_missing"]


def test_the_plan_says_the_hook_only_judges_the_commit(tmp_path):
    build(tmp_path, MINI)
    assert "IN THE COMMIT" in adopt(tmp_path).stdout


def test_apply_without_confirmation_writes_nothing(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    before = tree(tmp_path)
    r = adopt(tmp_path, "--apply")
    assert r.returncode == 2 and "--yes" in r.stderr
    assert tree(tmp_path) == before


def test_apply_yes_installs_and_leaves_notes_alone(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    before = tree(tmp_path)
    r = adopt(tmp_path, "--apply", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    after = tree(tmp_path)
    assert all(after[k] == v for k, v in before.items())
    assert {k for k in after} - set(before) == {"areas.txt", ".githooks/pre-commit",
                                                 ".cogiforge/baseline.json"}
    assert os.access(tmp_path / ".githooks" / "pre-commit", os.X_OK)
    base = json.loads((tmp_path / ".cogiforge" / "baseline.json").read_text())
    assert len(base["orphans"]) == 3
    assert str(tmp_path) not in json.dumps(base) and str(ROOT) not in json.dumps(base)  # no absolute path
    assert local_cfg(tmp_path, "cogiforge.home") == ROOT.as_posix()
    hp = subprocess.run(["git", "-C", str(tmp_path), "config", "--local", "core.hooksPath"],
                        capture_output=True, text=True).stdout.strip()
    assert hp == ".githooks"


def test_the_installed_hook_blocks_a_new_orphan_and_ignores_old_debt(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    assert adopt(tmp_path, "--apply", "--yes").returncode == 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "LEAK_BLOCKLIST": str(tmp_path / "absent.txt")}

    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True, text=True, env=env)
    git("add", "areas.txt", ".githooks", ".cogiforge", "Ideas/a.md")
    assert git("commit", "-m", "adopt").returncode == 0  # old orphans exist but are not in this commit
    (tmp_path / "Ideas" / "new.md").write_text("---\narea: ideas\n---\nnothing links here\n")
    git("add", "Ideas/new.md")
    r = git("commit", "-m", "orphan")
    assert r.returncode != 0 and "COMMIT BLOCKED" in r.stdout + r.stderr


def test_never_overwrites_an_existing_areas_file(tmp_path):
    build(tmp_path, {**MINI, "areas.txt": "mine: mine\n"})
    git_init(tmp_path)
    assert "CONFLICT" in adopt(tmp_path).stdout
    r = adopt(tmp_path, "--apply", "--yes")
    assert r.returncode == 1
    assert (tmp_path / "areas.txt").read_text() == "mine: mine\n"
    assert (tmp_path / ".cogiforge" / "baseline.json").is_file()  # the free items are still installed


FOREIGN = "#!/bin/sh\necho third-party hook runs\n"


def test_a_foreign_hook_is_not_activated_and_blocks_the_apply(tmp_path):
    build(tmp_path, {**MINI, ".githooks/pre-commit": FOREIGN})
    git_init(tmp_path)
    plan = adopt(tmp_path)
    assert plan.returncode == 1 and "third-party hook runs" in plan.stdout and "Read it" in plan.stdout
    before = tree(tmp_path)
    r = adopt(tmp_path, "--apply", "--yes")
    assert r.returncode == 1 and "NOT APPLIED" in r.stderr
    assert tree(tmp_path) == before
    assert local_cfg(tmp_path, "core.hooksPath") == "" and local_cfg(tmp_path, "cogiforge.home") == ""


def test_an_identical_hook_is_kept_and_activated(tmp_path):
    mod = load_module()
    build(tmp_path, {**MINI, ".githooks/pre-commit": mod.HOOK_TEXT})
    git_init(tmp_path)
    r = adopt(tmp_path, "--apply", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / ".githooks" / "pre-commit").read_text() == mod.HOOK_TEXT
    assert local_cfg(tmp_path, "core.hooksPath") == ".githooks"


def test_the_dry_run_prints_the_full_hook_text(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    out = adopt(tmp_path).stdout
    for line in load_module().HOOK_TEXT.splitlines():
        assert line in out


def test_a_planted_cogiforge_home_file_is_never_followed(tmp_path):
    evil = tmp_path / "evil"
    for f in ("ring", "gate", "leak"):
        build(evil / "core", {f"{f}.py": "import pathlib; pathlib.Path(__file__).parent.parent.joinpath('PWNED').write_text('x')\n"})
    v = tmp_path / "v"
    build(v, {**MINI, ".cogiforge/home": str(evil) + "\n"})
    git_init(v)
    assert adopt(v, "--apply", "--yes").returncode == 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "LEAK_BLOCKLIST": str(v / "absent.txt")}
    subprocess.run(["git", "-C", str(v), "add", "Ideas/a.md"], check=True)
    subprocess.run(["git", "-C", str(v), "commit", "-m", "x"], capture_output=True, env=env)
    assert not (evil / "PWNED").exists()  # the hook ran the real cogiforge, not the planted one


def _hook_run(v, home_value):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "LEAK_BLOCKLIST": str(v / "absent.txt")}
    if home_value is None:
        subprocess.run(["git", "-C", str(v), "config", "--local", "--unset", "cogiforge.home"], check=True)
    else:
        subprocess.run(["git", "-C", str(v), "config", "--local", "cogiforge.home", home_value], check=True)
    subprocess.run(["git", "-C", str(v), "add", "Ideas/a.md"], check=True)
    return subprocess.run(["git", "-C", str(v), "commit", "-m", "x"], capture_output=True, text=True, env=env)


def test_the_hook_refuses_an_invalid_cogiforge_home(tmp_path):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    assert adopt(v, "--apply", "--yes").returncode == 0
    empty = tmp_path / "emptydir"
    empty.mkdir()
    some_file = tmp_path / "f"
    some_file.write_text("x")
    for bad in (None, "relative/path", str(tmp_path / "missing"), str(some_file), str(empty)):
        r = _hook_run(v, bad)
        assert r.returncode != 0 and "COMMIT BLOCKED" in r.stdout + r.stderr, (bad, r.stdout, r.stderr)
    assert _hook_run(v, ROOT.as_posix()).returncode == 0  # the valid value passes


def test_a_vault_with_a_different_cogiforge_home_in_git_config_blocks_the_apply(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "config", "--local", "cogiforge.home", str(tmp_path / "other")], check=True)
    r = adopt(tmp_path, "--apply", "--yes")
    assert r.returncode == 1 and not (tmp_path / ".githooks").exists()


def test_not_a_git_repo_is_pending_and_never_runs_git_init(tmp_path):
    build(tmp_path, MINI)
    before = tree(tmp_path)
    assert adopt(tmp_path).returncode == 1
    r = adopt(tmp_path, "--apply", "--yes")
    assert r.returncode == 1 and "not a git repository" in (r.stdout + r.stderr)
    assert tree(tmp_path) == before and not (tmp_path / ".git").exists()


def test_empty_vault_says_nothing_to_adopt(tmp_path):
    build(tmp_path, {".obsidian/app.json": "{}", ".obsidian/x.md": "# x\n"})
    r = adopt(tmp_path)
    assert "nothing to adopt" in r.stdout and r.returncode == 1
    assert "OK" not in r.stdout.split("pending")[0].replace("dry run", "")


def test_missing_vault_is_rc_3(tmp_path):
    assert adopt(tmp_path / "nope").returncode == 3


def test_dataless_note_is_skipped_and_recorded(tmp_path, monkeypatch):
    build(tmp_path, MINI)
    mod = load_module()
    real = mod.is_dataless
    monkeypatch.setattr(mod, "is_dataless", lambda p: Path(p).name == "c.md" or real(p))
    plan = mod.build_plan(tmp_path)
    assert [r for r, _ in plan["skipped"]] == ["Work/c.md"]
    assert "Work/c.md" not in plan["debt"]["orphans"] and plan["debt"]["notes"] == 5
    assert any("skipped" in p for p in plan["pending"])
    assert "dataless" in mod.render(plan) and "SKIPPED" in mod.render(plan)


def test_the_real_dataless_predicate():
    mod = load_module()

    class St:  # st_blocks 0 with a size is a placeholder; an empty file is not
        pass
    real = os.lstat
    try:
        for blocks, size, want in ((0, 10, True), (0, 0, False), (8, 10, False)):
            st = St()
            st.st_blocks, st.st_size = blocks, size
            mod.os.lstat = lambda p, st=st: st
            assert mod.is_dataless("x") is want
    finally:
        mod.os.lstat = real


def test_unreadable_non_utf8_note_is_skipped(tmp_path):
    build(tmp_path, {**MINI, "Ideas/bad.md": b"\xff\xfe\x00bad \xff"})
    plan = json.loads(adopt(tmp_path, "--json").stdout)
    assert [r for r, _ in plan["skipped"]] == ["Ideas/bad.md"]
    assert plan["debt"]["notes"] == 6


def test_e2e_mini_vault_plan_text(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    out = adopt(tmp_path).stdout
    assert "orphan notes           3" in out and "dead wikilinks         1" in out
    assert "Ideas: ideas" in out and "Work: work" in out


# ---------------------------------------------------------------- hardening: untrusted vault

def plant_decoy(vault, tmp_path, lines):
    """A script that leaves a marker when run, and the `.git/config` lines that would make git run it."""
    marker = tmp_path / "MARKER"
    decoy = tmp_path / "decoy.sh"
    decoy.write_bytes(f"#!/bin/sh\ntouch '{marker.as_posix()}'\n".encode())  # bytes: no CRLF in a shell script
    decoy.chmod(0o755)
    with open(Path(vault) / ".git" / "config", "a", encoding="utf-8") as fh:
        fh.write(lines.format(decoy=decoy.as_posix()))
    return marker


RISKY_CONFIGS = {
    "fsmonitor": "[core]\n\tfsmonitor = {decoy}\n",
    "sshcommand": "[core]\n\tsshCommand = {decoy}\n",
    "pager": "[core]\n\tpager = {decoy}\n",
    "editor": "[core]\n\teditor = {decoy}\n",
    "alias": "[alias]\n\tst = !{decoy}\n",
    "diff-external": "[diff]\n\texternal = {decoy}\n",
    "filter": '[filter "x"]\n\tclean = {decoy}\n\tsmudge = {decoy}\n\tprocess = {decoy}\n',
    "credential": "[credential]\n\thelper = !{decoy}\n",
    "hookspath": "[core]\n\thooksPath = {decoy}\n",
    "include": "[include]\n\tpath = {decoy}\n",
    "same-line-section": "[core] fsmonitor = {decoy}\n",
    "upper-case": "[CORE]\n\tFsMonitor = {decoy}\n",
    "continuation": "[core]\n\tfilemode = true\n\tfsmonitor = \\\n{decoy}\n",
    "includeif": '[includeIf "gitdir:/"]\n\tpath = {decoy}\n',
    "quoted-subsection": '[filter "a b"]\n\tclean = {decoy}\n',
    "repeated-key": "[core]\n\tfilemode = true\n\tfilemode = {decoy}\n",
    "hookspath-dot-slash": "[core]\n\thooksPath = ./.githooks\n",
    "hookspath-normalizes": "[core]\n\thooksPath = .githooks/../../{decoy}\n",
    "quoted-value": '[core]\n\tpager = "{decoy}"\n',
    "comment-backslash": "# harmless comment \\\n[core]\n\tfsmonitor = {decoy}\n",
    "extensions": "[extensions]\n\tworktreeConfig = true\n",
    "bare-key": "[core]\n\tfilemode\n",
    "remote-ext-url": '[remote "o"]\n\turl = ext::{decoy}\n',
    "remote-pushurl": '[remote "o"]\n\tpushurl = https://example.com/x.git\n',
    "core-bare-true": "[core]\n\tbare = true\n",
    "format-version-1": "[core]\n\trepositoryformatversion = 1\n",
    "unknown-section": "[safe]\n\tdirectory = *\n",
    "key-before-section": "fsmonitor = {decoy}\n",
    "nul-byte": "[core]\n\tfilemode = true\x00\n",
    "ansi-in-value": "[user]\n\tname = \x1b[31mred\n",
}


def test_what_git_init_and_git_clone_write_is_accepted(tmp_path):
    build(tmp_path / "v", MINI)
    git_init(tmp_path / "v")
    with open(tmp_path / "v" / ".git" / "config", "a", encoding="utf-8") as fh:
        fh.write('[user]\n\tname = Ana Souza\n\temail = ana@example.com\n'
                 '[remote "origin"]\n\turl = https://example.com/x.git\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n'
                 '[branch "main"]\n\tremote = origin\n\tmerge = refs/heads/main\n# a comment\n')
    assert adopt(tmp_path / "v", "--apply", "--yes").returncode == 0
    # a real clone
    src = tmp_path / "src"
    build(src, MINI)
    git_init(src)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "-C", str(src), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(src), "commit", "-qm", "i"], check=True, env=env)
    subprocess.run(["git", "clone", "-q", str(src), str(tmp_path / "clone")], check=True)
    r = adopt(tmp_path / "clone", "--apply", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_validator_unit(tmp_path):
    m = load_module()
    ok = lambda text: not m.validate_git_config(text.encode())[1]  # noqa: E731
    assert ok("[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n\tlogallrefupdates = true\n")
    assert ok("[core]\n\thooksPath = .githooks\n[cogiforge]\n\thome = " + ROOT.as_posix() + "\n")
    assert ok("[core]\n\tfilemode = true # a comment git itself understands\n")  # git says value=true, so it is judged as true
    assert ok('[remote "origin"]\n\turl = C:\\\\Users\\\\ana\\\\repo\n')  # a local clone path on Windows
    assert not ok('[remote "origin"]\n\turl = C:$HOME\n')
    assert not ok("[cogiforge]\n\thome = /somewhere/else\n")
    assert not ok("[core]\n\tfsmonitor = true\n")           # even the harmless-looking value: not in the allowlist
    assert not ok("[core]\n\tfilemode=TRUE\n")               # exact values only
    assert not ok("[core]\n\tfilemode\n")                    # key without a value
    assert not ok("[core\n")                                  # git itself rejects it
    viol = m.validate_git_config(b"[core]\n\tfsmonitor = /x\n")[1]
    assert viol and viol[0][0] == "core.fsmonitor" and viol[0][1] == "/x"  # the entry is cited
    assert not m.validate_git_config(b"\xff\xfe")[0] and m.validate_git_config(b"x" * 70000)[1]


def test_each_variant_is_blocked_with_the_line_cited_and_nothing_executes(tmp_path):
    # the decoy script path is ABSOLUTE and already expanded (format), never a `$VAR` that would prove nothing
    for name, cfg in RISKY_CONFIGS.items():
        v = tmp_path / name
        build(v, MINI)
        git_init(v)
        marker = plant_decoy(v, tmp_path, cfg)
        assert tmp_path.as_posix() in (v / ".git" / "config").read_text(encoding="utf-8") or "{decoy}" not in cfg, name
        before = tree(v)
        plan = adopt(v)
        assert plan.returncode == 1 and "allowlist" in plan.stdout and "entry" in plan.stdout, (name, plan.stdout[-600:])
        r = adopt(v, "--apply", "--yes")
        assert r.returncode == 1 and "NOT APPLIED" in r.stderr, (name, r.stderr)
        assert tree(v) == before and not marker.exists(), name
        assert not (v / ".githooks").exists() and "cogiforge" not in (v / ".git" / "config").read_text(encoding="utf-8")


def _plain_git_runs_decoy(kind, tmp_path):
    v = tmp_path / ("ctl-" + kind)
    build(v, MINI)
    git_init(v)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}

    def git(*a):
        return subprocess.run(["git", "-C", str(v), *a], capture_output=True, text=True, env=env)
    git("add", "-A")
    git("commit", "-qm", "i")
    marker = plant_decoy(v, tmp_path, RISKY_CONFIGS[{"fsmonitor": "fsmonitor", "alias": "alias", "filter": "filter",
                                                     "diff": "diff-external"}[kind]])
    if kind == "fsmonitor":
        git("status")
    elif kind == "alias":
        git("st")
    elif kind == "filter":
        (v / ".gitattributes").write_text("* filter=x\n")
        (v / "Ideas" / "a.md").write_text("changed\n")
        git("add", "Ideas/a.md")
    elif kind == "diff":
        (v / "Ideas" / "a.md").write_text("changed again\n")
        git("diff", "--ext-diff")
    return marker.exists()


def test_controls_plain_git_does_run_the_decoy(tmp_path):
    """The risk is real: plain git executes each of these. Without this, the block tests above would prove nothing."""
    results = {k: _plain_git_runs_decoy(k, tmp_path) for k in ("fsmonitor", "alias", "filter", "diff")}
    assert all(results.values()), results


def test_git_dir_that_is_a_symlink_or_file_is_unsafe(tmp_path):
    real = tmp_path / "elsewhere"
    real.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=real, check=True)
    v = tmp_path / "v"
    build(v, MINI)
    (v / ".git").symlink_to(real / ".git")
    before = tree(v)
    r = adopt(v, "--apply", "--yes")
    assert r.returncode == 1 and tree(v) == before and not (real / ".githooks").exists()
    w = tmp_path / "w"
    build(w, {**MINI, ".git": "gitdir: /somewhere/else\n"})
    assert adopt(w, "--apply", "--yes").returncode == 1 and not (w / ".githooks").exists()


def test_a_symlinked_githooks_or_cogiforge_folder_is_never_written_through(tmp_path):
    for name in (".githooks", ".cogiforge"):
        out = tmp_path / ("outside" + name)
        out.mkdir()
        v = tmp_path / ("v" + name)
        build(v, MINI)
        git_init(v)
        (v / name).symlink_to(out)
        r = adopt(v, "--apply", "--yes")
        assert r.returncode == 1 and not any(out.iterdir()), name


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes (os.mkfifo) do not exist on Windows")
def test_a_fifo_named_md_is_skipped_and_never_opened(tmp_path):
    build(tmp_path, MINI)
    os.mkfifo(tmp_path / "Ideas" / "pipe.md")
    r = subprocess.run([sys.executable, ADOPT, str(tmp_path), "--json"], capture_output=True, text=True, timeout=30,
                       stdin=subprocess.DEVNULL)
    plan = json.loads(r.stdout)
    assert [p for p, _ in plan["skipped"]] == ["Ideas/pipe.md"] and plan["debt"]["notes"] == 6


def test_a_note_name_starting_with_a_dash_is_not_an_option_for_the_hook(tmp_path):
    v = tmp_path / "v"
    build(v, {**MINI, "-x.md": "links to [[a]] and [[ghost-nowhere]]\n"})
    git_init(v)
    assert adopt(v, "--apply", "--yes").returncode == 0
    r = _hook_run(v, ROOT.as_posix())  # stages Ideas/a.md only
    assert r.returncode == 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "LEAK_BLOCKLIST": str(v / "absent.txt")}
    subprocess.run(["git", "-C", str(v), "add", "--", "-x.md"], check=True)
    r = subprocess.run(["git", "-C", str(v), "commit", "-m", "dash"], capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "ghost-nowhere" in out and "unrecognized arguments" not in out  # judged as a note


def test_yes_never_skips_the_plan_or_the_blocks(tmp_path):
    build(tmp_path, MINI)  # not a git repo: --yes alone must not write
    r = adopt(tmp_path, "--apply", "--yes")
    assert "adopt plan for" in r.stdout and r.returncode == 1 and not (tmp_path / ".cogiforge").exists()
    assert adopt(tmp_path, "--yes").returncode == 2  # --yes without --apply is a usage error


def test_other_files_in_githooks_block_even_with_our_identical_hook(tmp_path):
    m = load_module()
    for extra in ("post-checkout", "prepare-commit-msg", "sub/x"):
        v = tmp_path / extra.replace("/", "_")
        build(v, {**MINI, ".githooks/pre-commit": m.HOOK_TEXT, f".githooks/{extra}": "#!/bin/sh\necho hostile\n"})
        git_init(v)
        before = tree(v)
        r = adopt(v, "--apply", "--yes")
        assert r.returncode == 1 and "other files" in (r.stdout + r.stderr) and tree(v) == before, extra
        assert local_cfg(v, "core.hooksPath") == ""


def test_a_dangling_areas_symlink_is_a_conflict_and_never_written_through(tmp_path):
    build(tmp_path / "v", MINI)
    git_init(tmp_path / "v")
    target = tmp_path / "outside.txt"
    (tmp_path / "v" / "areas.txt").symlink_to(target)
    r = adopt(tmp_path / "v", "--apply", "--yes")
    assert r.returncode == 1 and not target.exists()


def test_apply_rechecks_the_disk_after_the_plan(tmp_path):
    build(tmp_path, MINI)
    git_init(tmp_path)
    m = load_module()
    plan = m.build_plan(tmp_path)
    assert not plan["blocking"]
    marker = plant_decoy(tmp_path, tmp_path, RISKY_CONFIGS["fsmonitor"])  # hostile config appears after the plan
    import pytest
    with pytest.raises(m.Blocked):
        m.apply(plan, tmp_path)
    assert not (tmp_path / ".githooks").exists() and not marker.exists()


def test_an_unsafe_checkout_path_blocks(tmp_path, monkeypatch):
    build(tmp_path, MINI)
    git_init(tmp_path)
    m = load_module()
    monkeypatch.setattr(m, "ROOT", Path('/tmp/a"b'))
    assert any("cannot verify" in b for b in m.guard(tmp_path)["blocking"])


def test_the_hook_refuses_a_noncanonical_cogiforge_home(tmp_path):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    assert adopt(v, "--apply", "--yes").returncode == 0
    link = tmp_path / "link-to-root"
    link.symlink_to(ROOT)
    for bad in (ROOT.as_posix() + "/../" + ROOT.name, ROOT.as_posix() + "/", ROOT.as_posix() + "/./", link.as_posix(), "/" + ROOT.as_posix()):
        r = _hook_run(v, bad)
        assert r.returncode != 0 and "COMMIT BLOCKED" in r.stdout + r.stderr, (bad, r.stdout + r.stderr)
    assert _hook_run(v, ROOT.as_posix()).returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="Windows forbids newline/control characters in file names, so the hostile file cannot be created")
def test_hostile_names_never_reach_the_terminal_raw_nor_areas_txt(tmp_path):
    build(tmp_path, {**MINI, "Evil\nFolder/n.md": "x\n", "Spaced Folder/s.md": "y\n", "x\nFAKE LINE.md": "z\n",
                     "\x1b[31mred.md": "r\n"})
    plan = json.loads(adopt(tmp_path, "--json").stdout)
    assert "Evil\nFolder" not in plan["areas"] and "Spaced Folder" in plan["areas"]
    out = adopt(tmp_path).stdout
    assert "\nFAKE LINE" not in out and "\x1b" not in out
    git_init(tmp_path)
    assert adopt(tmp_path, "--apply", "--yes").returncode in (0, 1)
    areas = (tmp_path / "areas.txt").read_text(encoding="utf-8")
    assert "Evil" not in areas and all(":" in l for l in areas.splitlines() if l and not l.startswith("#"))


@pytest.mark.skipif(sys.platform == "win32", reason="Windows forbids newline/control characters in file names, so the hostile file cannot be created")
def test_a_note_with_a_newline_or_space_in_its_name_is_judged_by_the_hook(tmp_path):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    assert adopt(v, "--apply", "--yes").returncode == 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "LEAK_BLOCKLIST": str(v / "absent.txt")}
    for name in ("Ideas/with space.md", "Ideas/new\nline.md"):
        build(v, {name: "---\narea: ideas\n---\nsee [[a]] and [[ghost-nl]]\n"})
        subprocess.run(["git", "-C", str(v), "add", "--", name], check=True)
        r = subprocess.run(["git", "-C", str(v), "commit", "-m", "n"], capture_output=True, text=True, env=env)
        assert r.returncode != 0 and "ghost-nl" in r.stdout + r.stderr, (name, r.stdout + r.stderr)
        subprocess.run(["git", "-C", str(v), "reset", "-q"], check=True)


# ---------------------------------------------------------------- the parser is git itself: differential tests

import random  # noqa: E402
import re  # noqa: E402
import unicodedata  # noqa: E402

# Written here on purpose, independent of the allowlist in adopt.py: what the TEST believes git init/clone may carry.
TEST_OK_KEY = re.compile(
    r"core\.(repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode|symlinks|hookspath)"
    r"|user\.(name|email)|cogiforge\.home|remote\.[^\s]+\.(url|fetch)|branch\.[^\s]+\.(remote|merge)")
DANGEROUS = re.compile(r"fsmonitor|sshcommand|pager|editor|askpass|alias\.|filter\.|include|external|textconv|helper|"
                       r"\.driver|\.command|\.process|\.clean|\.smudge|extensions|hookspath", re.I)


def git_lists(text, tmp_path):
    """What git itself says about this config text: ([(key, value)], error). An independent call, not adopt's."""
    f = tmp_path / "cfg-under-test"
    f.write_bytes(text.encode("utf-8", "surrogateescape"))
    r = subprocess.run(["git", "config", "--file", str(f), "--list", "-z", "--no-includes"], capture_output=True,
                       cwd=str(tmp_path), env={"PATH": os.environ["PATH"], "HOME": str(tmp_path),
                                               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if r.returncode != 0:
        return None, r.stderr.decode()
    pairs = []
    for rec in r.stdout.decode("utf-8", "replace").split("\0"):
        if rec:
            k, nl, v = rec.partition("\n")
            pairs.append((k, v if nl else None))
    return pairs, None


def check_differential(m, text, tmp_path):
    pairs, err = git_lists(text, tmp_path)
    entries, viol = m.validate_git_config(text.encode("utf-8", "surrogateescape"))
    if pairs is None:
        assert viol, ("git rejects it but adopt accepted", text)
        return False
    approved = not viol
    if approved:
        for k, v in pairs:  # NO approved config carries a key outside the allowlist, according to git
            assert TEST_OK_KEY.fullmatch(k) and v is not None, ("approved but git lists", k, text)
            assert not DANGEROUS.search(k) or k in ("core.hookspath",), (k, text)
            if k == "core.hookspath":
                assert v == ".githooks"
    if any(not TEST_OK_KEY.fullmatch(k) for k, _ in pairs):
        assert viol, ("git lists a key outside the allowlist, adopt approved", pairs, text)
    return approved


ESCAPES = [
    "[core]\n\tfilemode = true\n",
    '[core]\n\tfilemode = "true"\n',
    "[core]\n\tfilemode = tr\\\nue\n",
    "[core]\n\tfilemode = tr\\\n\tue\n",
    "[user]\n\tname = A\\nB\n",
    '[user]\n\tname = "x\\ty"\n',
    "[user]\n\tname = a # c\n",
    "[user]\n\tname = a ; c\n",
    "[core.a.b]\n\tfsmonitor = /x\n",
    '[core "a.b"]\n\tfsmonitor = /x\n',
    "[a.b]\n\tc = 1\n",
    '[a "b"]\n\tc = 1\n',
    '[remote "o.p"]\n\turl = https://example.com/x.git\n',
    "[remote.o]\n\turl = https://example.com/x.git\n",
    '[remote "o"]\n\turl = ext::sh -c x\n',
    '[branch "a/b.c"]\n\tremote = origin\n\tmerge = refs/heads/a/b.c\n',
    "[core]\n\tbare\n",
    "[core]\n\t=true\n",
    "[core]\n\tfilemode = true\n\tfilemode = false\n",
    "[core]\n\thooksPath = .githooks\n",
    "[core]\n\thooksPath = ./.githooks\n",
    "[CORE]\n\tFILEMODE = TRUE\n",
    "﻿[core]\n\tfilemode = true\n",
    "[core]\r\n\tfilemode = true\r\n",
    "# only a comment\n",
    "",
    "[core]\n\tfilemode = true\n[include]\n\tpath = /x\n",
    '[includeIf "gitdir:/"]\n\tpath = /x\n',
    "[remote",
    '[core "unterminated]\n',
]


def test_the_variants_and_escapes_agree_with_what_git_lists(tmp_path):
    m = load_module()
    texts = [cfg.format(decoy=tmp_path / "decoy.sh") for cfg in RISKY_CONFIGS.values()] + ESCAPES
    approved = [check_differential(m, t, tmp_path) for t in texts]
    assert any(approved) and not all(approved)  # the property is not vacuous: some pass, some do not


def test_fuzz_no_approved_config_carries_a_key_outside_the_allowlist(tmp_path):
    m = load_module()
    decoy = tmp_path / "decoy.sh"
    heads = ["[core]", "[CORE]", '[core "a.b"]', "[core.a.b]", '[remote "o"]', "[remote.o]", '[branch "main"]', "[user]",
             "[include]", '[filter "x"]', "[a]", "[a.b]", '[a "b"]', "[cogiforge]", "[core]", "[user]", '[remote "o"]']
    keys = ["\tfilemode = true", "\tFileMode=false", "\tbare = false", '\tbare = "false"', "\tbare = fal\\\nse",
            "\turl = https://example.com/x.git", f"\turl = ext::{decoy}", "\tfetch = +refs/heads/*:refs/remotes/o/*",
            "\tremote = origin", "\tmerge = refs/heads/main", "\tname = Ana", "\tname = A\\nB", '\tname = "x\\ty"',
            "\temail = " + "a" + "@" + "b.co", f"\thome = {ROOT}", "\thookspath = .githooks", f"\tfsmonitor = {decoy}", f"\tpath = {decoy}",
            f"\tclean = {decoy}", "\tkey", "\t# comment", "; comment", "\tfilemode = true ; c", "\trepositoryformatversion = 0",
            "\tx.y = 1", f"\tpager = {decoy}", "\thooksPath = ./.githooks", "\tlogallrefupdates = true", "", "   "]
    rnd = random.Random(20261007)
    ok = 0
    for _ in range(300):
        lines = []
        for _ in range(rnd.randint(1, 7)):
            lines.append(rnd.choice(heads))
            lines += [rnd.choice(keys) for _ in range(rnd.randint(0, 3))]
        text = "\n".join(lines) + "\n"
        ok += check_differential(m, text, tmp_path)
    assert 20 < ok < 300, ok  # some accepted, some blocked: the property was exercised both ways


def test_the_git_parser_executes_none_of_the_decoys(tmp_path):
    m = load_module()
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    markers = []
    for kind in ("fsmonitor", "alias", "filter", "diff-external", "credential", "pager", "sshcommand", "include"):
        markers.append(plant_decoy(v, tmp_path, RISKY_CONFIGS[kind]))
    data = (v / ".git" / "config").read_bytes()
    entries, viol = m.validate_git_config(data)
    assert viol and not any(mk.exists() for mk in markers)
    assert adopt(v, "--apply", "--yes").returncode == 1 and not any(mk.exists() for mk in markers)
    # (the control that plain git DOES run these decoys is test_controls_plain_git_does_run_the_decoy)


# ---------------------------------------------------------------- terminal escapes

BAD = "\x1b\x9b\x07\x7f‮⁦​‏ \ud800\x00"


def raw_control(text):
    return [c for c in text if c != "\n" and (unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs") or ord(c) == 0x7F)]


def test_safe_escapes_every_control_format_and_surrogate_character():
    m = load_module()
    for c in BAD:
        out = m.safe("a" + c + "b")
        assert not raw_control(out), repr(c)
        assert "\\x" in out or "\\u" in out
    assert m.safe("\x1b]0;x\x07") == "\\x1b]0;x\\x07" and m.safe("\x9b") == "\\x9b" and m.safe("‮") == "\\u202e"
    assert m.safe("caf\u00e9 \u65e5\u672c") == "caf\u00e9 \u65e5\u672c"  # printable text is untouched
    assert m.safe("\n") == "\\x0a"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows forbids newline/control characters in file names, so the hostile file cannot be created")
def test_untrusted_text_never_reaches_the_terminal_raw(tmp_path):
    m = load_module()
    esc = "\x1b]0;PWNED\x07"
    v = tmp_path / "v"
    build(v, {**MINI, f"n{esc}.md": "x\n", "b\u009b31m.md": "y\n", "r‮txt.md": "z\n", f"Dir{esc}/in.md": "w\n",
              ".githooks/pre-commit": f"#!/bin/sh\necho {esc} hostile ‮\n"})
    git_init(v)
    with open(v / ".git" / "config", "a", encoding="utf-8") as fh:
        fh.write(f"[core]\n\tpager = {esc}{tmp_path}/decoy.sh\n")
    assert esc in (v / ".githooks" / "pre-commit").read_text(encoding="utf-8")  # control: the bait is really in the vault
    for args in ((), ("--apply", "--yes"), ("--apply",)):
        r = adopt(v, *args)
        assert not raw_control(r.stdout + r.stderr), (args, [hex(ord(c)) for c in raw_control(r.stdout + r.stderr)])
        assert "\\x1b" in r.stdout  # shown, visibly escaped
    r = adopt(v, "--json")
    assert not raw_control(r.stdout) and json.loads(r.stdout)["vault"]  # still valid JSON


def test_the_json_output_is_ascii_and_valid_for_hostile_names(tmp_path):
    build(tmp_path, {**MINI, "x\u009b‮.md": "z\n"})
    r = adopt(tmp_path, "--json")
    assert r.stdout.isascii() and any("\\u009b" in r.stdout or "\\u202e" in r.stdout for _ in [0]) and json.loads(r.stdout)


def test_the_installed_hook_output_has_no_control_characters(tmp_path):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    assert adopt(v, "--apply", "--yes").returncode == 0
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "LEAK_BLOCKLIST": str(v / "absent.txt")}
    note = v / "Ideas" / "esc.md"
    note.write_text("---\narea: ideas\n---\nsee [[a]] and [[gh\x1b[31mo\x1b]0;PWNED\x07st]]\n", encoding="utf-8")
    ctl = subprocess.run([sys.executable, str(ROOT / "core" / "gate.py"), "--vault", str(v), str(note)],
                         capture_output=True, text=True, cwd=str(v))
    assert "\x1b" in ctl.stdout  # control: the gate does echo the bait, so the hook has something to sanitize
    subprocess.run(["git", "-C", str(v), "add", "Ideas/esc.md"], check=True)
    r = subprocess.run(["git", "-C", str(v), "commit", "-m", "x"], capture_output=True, text=True, env=env)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "COMMIT BLOCKED" in out and not raw_control(out), [hex(ord(c)) for c in raw_control(out)]


# ---------------------------------------------------------------- .git is judged as a whole (reproduced on main: commondir)

def make_evil_gitdir(tmp_path, name="evil"):
    """A real repository whose config makes git run the decoy (absolute path, already expanded)."""
    e = tmp_path / name
    e.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=e, check=True)
    marker = plant_decoy(e, tmp_path, "[core]\n\tfsmonitor = {decoy}\n")
    return e / ".git", marker


def run_plain_git(v):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    for args in (("status",), ("add", "Ideas/a.md"), ("commit", "-qm", "x"), ("diff",)):
        subprocess.run(["git", "-C", str(v), *args], capture_output=True, env=env)


def test_commondir_indirection_is_blocked_and_plain_git_does_run_through_it(tmp_path):
    for how in ("absolute", "relative"):
        v = tmp_path / ("v-" + how)
        build(v, MINI)
        git_init(v)
        evil, marker = make_evil_gitdir(tmp_path, "evil-" + how)
        target = str(evil) if how == "absolute" else os.path.relpath(evil, v / ".git")
        (v / ".git" / "commondir").write_text(target + "\n")
        # CONTROL: this is the hole. Plain git, on this very layout, executes the decoy from the other repository's config.
        run_plain_git(v)
        assert marker.exists(), how
        marker.unlink()
        before = tree(v)
        plan = adopt(v)
        assert plan.returncode == 1 and "commondir" in plan.stdout, how
        r = adopt(v, "--apply", "--yes")
        assert r.returncode == 1 and "NOT APPLIED" in r.stderr and tree(v) == before, how
        assert not marker.exists() and not (v / ".githooks").exists(), how


def _w(path, text="x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


EXTRAS = {
    "config.worktree": lambda g, t: _w(g / "config.worktree", "[core]\n\tfsmonitor = x\n"),
    "modules": lambda g, t: (g / "modules").mkdir(),
    "worktrees": lambda g, t: (g / "worktrees").mkdir(),
    "shallow": lambda g, t: _w(g / "shallow"),
    "gitdir": lambda g, t: _w(g / "gitdir", "/elsewhere/.git\n"),
    "rebase-merge": lambda g, t: _w(g / "rebase-merge" / "git-rebase-todo", "exec echo hostile\n"),
    "MERGE_HEAD": lambda g, t: _w(g / "MERGE_HEAD", "0" * 40 + "\n"),
    "sequencer": lambda g, t: _w(g / "sequencer" / "todo", "exec echo hostile\n"),
    "info/attributes": lambda g, t: _w(g / "info" / "attributes", "* filter=x\n"),
    "info/grafts": lambda g, t: _w(g / "info" / "grafts"),
    "objects/info/alternates": lambda g, t: _w(g / "objects" / "info" / "alternates", str(t) + "\n"),
    "hooks/pre-commit": lambda g, t: (_w(g / "hooks" / "pre-commit", "#!/bin/sh\nexit 0\n"), (g / "hooks" / "pre-commit").chmod(0o755)),
    "refs symlink": lambda g, t: (g / "refs" / "heads" / "link").symlink_to(t),
    "HEAD hostile": lambda g, t: _w(g / "HEAD", "ref: refs/heads/x\ncore.fsmonitor\n"),
    "stray file": lambda g, t: _w(g / "whatever"),
    "index.lock": lambda g, t: _w(g / "index.lock"),
    "top symlink": lambda g, t: (g / "description").unlink() or (g / "description").symlink_to(t),
}


def test_every_extra_thing_in_dot_git_blocks_and_nothing_is_written(tmp_path):
    for name, setup in EXTRAS.items():
        v = tmp_path / name.replace("/", "_").replace(" ", "_")
        build(v, MINI)
        git_init(v)
        setup(v / ".git", tmp_path)
        before = tree(v)
        r = adopt(v, "--apply", "--yes")
        assert r.returncode == 1 and "NOT APPLIED" in r.stderr and "plain repository" in r.stderr, (name, r.stderr[-500:])
        assert tree(v) == before and local_cfg(v, "core.hooksPath") == "", name


def test_a_plain_repository_with_history_is_accepted(tmp_path):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "-C", str(v), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(v), "commit", "-qm", "one"], check=True, env=env)
    subprocess.run(["git", "-C", str(v), "commit", "-q", "--amend", "-m", "two"], check=True, env=env)
    subprocess.run(["git", "-C", str(v), "gc", "-q"], check=True, env=env)
    (v / ".git" / "info").mkdir(exist_ok=True)
    (v / ".git" / "info" / "exclude").write_text("*.tmp\n")
    r = adopt(v, "--apply", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_relative_vault_path_works_from_inside_the_vault(tmp_path):
    """Reproduced on main: `adopt .` crashed after writing files (the config path was relative to a temp folder)."""
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    for arg, cwd in (("." , v), ("v", tmp_path)):
        r = subprocess.run([sys.executable, ADOPT, arg, "--apply", "--yes"], capture_output=True, text=True, cwd=str(cwd),
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdin=subprocess.DEVNULL)
        assert r.returncode == 0 and "Traceback" not in r.stderr, (arg, r.stdout[-300:], r.stderr)
        assert local_cfg(v, "core.hooksPath") == ".githooks" and local_cfg(v, "cogiforge.home") == ROOT.as_posix()
        subprocess.run(["git", "-C", str(v), "config", "--local", "--remove-section", "cogiforge"], check=True)
        subprocess.run(["git", "-C", str(v), "config", "--local", "--unset", "core.hooksPath"], check=True)
        for f in ("areas.txt", ".githooks", ".cogiforge"):
            p = v / f
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
            else:
                p.unlink()


def test_if_git_fails_the_config_is_written_first_so_nothing_else_is(tmp_path, monkeypatch):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    m = load_module()

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "git")
    monkeypatch.setattr(m, "write_local_config", boom)
    before = tree(v)
    rc = m.run(m.parser().parse_args([str(v), "--apply", "--yes"]))
    assert rc == 1 and tree(v) == before


def test_a_vault_that_changes_during_the_apply_is_reported(tmp_path, monkeypatch):
    v = tmp_path / "v"
    build(v, MINI)
    git_init(v)
    evil, marker = make_evil_gitdir(tmp_path)
    m = load_module()
    real = m.apply

    def apply_then_tamper(plan, vault):
        out = real(plan, vault)
        (Path(vault) / ".git" / "commondir").write_text(str(evil) + "\n")
        return out
    monkeypatch.setattr(m, "apply", apply_then_tamper)
    assert m.run(m.parser().parse_args([str(v), "--apply", "--yes"])) == 1
    assert not marker.exists()


def test_remote_urls_that_could_smuggle_an_ssh_option_are_not_accepted():
    m = load_module()
    ok = lambda u: not m.validate_git_config(f'[remote "o"]\n\turl = {u}\n'.encode())[1]  # noqa: E731
    for good in ("https://example.com/x.git", "ssh://git@example.com:22/x.git", "git@example.com:x/y.git",
                 "git://example.com/x.git", "./sub", "/abs/sub"):
        assert ok(good), good
    for bad in ("-Fevil@h:p", "-ofoo@h:p", "ssh://x@-Fevil/p", "ssh://-Fevil/p", "x@-Fevil:p", "_x@-h:p", "ext::sh -c x",
                "file:///x", "https://h/--upload-pack=x", "ssh://h/--upload-pack=x", "-oProxyCommand=x"):
        assert not ok(bad), bad
