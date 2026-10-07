"""Paired tests for tools/adopt.py. ADOPT_PATH points to another copy (used by mutation).

Every test builds a small synthetic vault in tmp and runs the real command line.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

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
    assert local_cfg(tmp_path, "cogiforge.home") == str(ROOT)
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
    assert _hook_run(v, str(ROOT)).returncode == 0  # the valid value passes


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
