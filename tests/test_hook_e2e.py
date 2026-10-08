"""End to end: a temporary clone, `sh install.sh`, and real commits."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LEAK = "/Users/" + "jdoe"  # assembled here so this file does not accuse itself


def sh(cwd, *cmd, env=None):
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "LEAK_BLOCKLIST": str(cwd / "no-list.txt"), **(env or {})})


@pytest.fixture
def clone(tmp_path):
    repo = tmp_path / "clone"
    repo.mkdir()
    for item in ("core", ".githooks", "install.sh", "vault", ".gitignore", ".leakignore"):
        source = ROOT / item
        if source.is_dir():
            shutil.copytree(source, repo / item, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(source, repo / item)
    sh(repo, "git", "init", "-q")
    sh(repo, "git", "config", "user.name", "test")
    sh(repo, "git", "config", "user.email", "test@example.com")
    r = sh(repo, "sh", "install.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    sh(repo, "git", "add", "-A")
    r = sh(repo, "git", "commit", "-q", "-m", "skeleton")
    assert r.returncode == 0, r.stdout + r.stderr
    return repo


def commit(repo, rel, text, *extra, env=None):
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")
    sh(repo, "git", "add", rel)
    return sh(repo, "git", "commit", "-q", "-m", "x", *extra, env=env)


ORPHAN = "---\narea: life\n---\n# Note without an edge\n\nText without a link.\n"


def test_install_activates_the_hookspath(clone):
    assert sh(clone, "git", "config", "--get", "core.hooksPath").stdout.strip() == ".githooks"


def test_orphan_blocks_the_commit_and_teaches(clone):
    r = commit(clone, "vault/notes/life/orphan.md", ORPHAN)
    assert r.returncode == 1
    assert "COMMIT BLOCKED" in r.stdout + r.stderr and "How to fix" in r.stdout + r.stderr


def test_with_the_wikilink_the_commit_passes(clone):
    r = commit(clone, "vault/notes/life/orphan.md", ORPHAN + "\nBack to [[home]].\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_without_hookspath_the_hook_does_not_fire(clone):
    sh(clone, "git", "config", "--unset", "core.hooksPath")
    assert commit(clone, "vault/notes/life/orphan.md", ORPHAN).returncode == 0


def test_no_verify_is_the_deliberate_bypass(clone):
    assert commit(clone, "vault/notes/life/orphan.md", ORPHAN, "--no-verify").returncode == 0


def test_inbox_is_never_blocked(clone):
    assert commit(clone, "vault/inbox/idea.md", "# loose idea, no link\n").returncode == 0


def test_orphan_outside_the_commit_only_warns(clone):
    (clone / "vault/notes/life/old.md").write_text(ORPHAN, encoding="utf-8")  # does not enter the stage
    r = commit(clone, "vault/notes/life/ok.md", "---\narea: life\n---\n# Linked\n\n[[home]]\n")
    assert r.returncode == 0 and "WARNING" in r.stdout + r.stderr and "old.md" in r.stdout + r.stderr


def set_gate(repo, text):
    (repo / "vault" / "gate.txt").write_text(text, encoding="utf-8")
    sh(repo, "git", "add", "vault/gate.txt")
    sh(repo, "git", "commit", "-q", "--no-verify", "-m", "gate config")


def test_shipped_gate_txt_is_block(clone):
    text = (clone / "vault" / "gate.txt").read_text(encoding="utf-8")
    assert "orphan: block" in text.splitlines()
    assert commit(clone, "vault/notes/life/orphan.md", ORPHAN).returncode == 1


def test_gate_txt_removed_still_blocks(clone):
    (clone / "vault" / "gate.txt").unlink()
    assert commit(clone, "vault/notes/life/orphan.md", ORPHAN).returncode == 1


def test_orphan_warn_lets_the_commit_through_and_prints_the_warning(clone):
    set_gate(clone, "orphan: warn\n")
    r = commit(clone, "vault/notes/life/orphan.md", ORPHAN)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "WARNING" in out and "orphan.md" in out and "COMMIT BLOCKED" not in out


def test_malformed_gate_txt_blocks_the_commit(clone):
    set_gate(clone, "orphan: maybe\n")
    r = commit(clone, "vault/notes/life/ok.md", "---\narea: life\n---\n# Linked\n\n[[home]]\n")
    out = r.stdout + r.stderr
    assert r.returncode == 1 and "COMMIT BLOCKED" in out and "gate.txt" in out


def test_leak_still_blocks_with_orphan_warn(clone):
    set_gate(clone, "orphan: warn\n")
    r = commit(clone, "vault/notes/life/v.md", f"---\narea: life\n---\n# V\n\n[[home]] {LEAK}\n")
    assert r.returncode == 1 and "leak" in (r.stdout + r.stderr).lower()
    r = commit(clone, "docs/note.txt", f"opened {LEAK}/x\n")
    assert r.returncode == 1


def test_leak_in_the_stage_blocks_any_file(clone):
    r = commit(clone, "docs/note.txt", f"opened {LEAK}/x\n")
    assert r.returncode == 1 and "leak" in (r.stdout + r.stderr).lower()
    assert "jdoe" not in r.stdout + r.stderr


def test_leak_in_a_vault_md_also_blocks(clone):
    r = commit(clone, "vault/notes/life/v.md", f"---\narea: life\n---\n# V\n\n[[home]] {LEAK}\n")
    assert r.returncode == 1


def test_without_a_private_list_warns_not_verified_and_does_not_block(clone):
    r = commit(clone, "docs/ok.txt", "clean\n")
    assert r.returncode == 0 and "NOT_VERIFIED" in r.stdout + r.stderr


def test_old_private_list_name_warns_in_the_hook_but_does_not_block(clone, tmp_path):
    home = tmp_path / "home"
    (home / ".config" / "cogiforge").mkdir(parents=True)
    (home / ".config" / "cogiforge" / "negra.txt").write_text("zeta-quux\n", encoding="utf-8")
    env = {"HOME": str(home), "LEAK_BLOCKLIST": ""}  # empty: falls back to the default location
    r = commit(clone, "docs/ok.txt", "plausible clean text\n", env=env)
    assert r.returncode == 0 and "WARNING" in r.stdout + r.stderr and "renamed" in r.stdout + r.stderr
    r = commit(clone, "docs/bad.txt", "talks about zeta-quux\n", env=env)
    assert r.returncode == 1


def test_solo_mode_ignores_people_folders(clone):
    # no vault/roles.txt: the people guard is silent, whoever commits and wherever
    r = commit(clone, "vault/people/_template/memory/extra.md", "# x\n\n[[home]]\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_incomplete_installation_fails_loudly(clone):
    (clone / "core" / "ring.py").unlink()
    r = commit(clone, "docs/ok.txt", "clean\n")
    assert r.returncode == 1 and "install.sh" in r.stdout + r.stderr


# ---- install.sh fails loudly ---------------------------------------------------

def test_install_outside_a_git_repo_fails(tmp_path):
    for item in ("core", ".githooks", "install.sh"):
        source = ROOT / item
        shutil.copytree(source, tmp_path / item, ignore=shutil.ignore_patterns("__pycache__")) if source.is_dir() else shutil.copy(source, tmp_path / item)
    r = sh(tmp_path, "sh", "install.sh", env={"GIT_CEILING_DIRECTORIES": str(tmp_path.parent)})
    assert r.returncode != 0 and "git repository" in r.stdout + r.stderr


def test_install_with_a_broken_selftest_fails(clone):
    sh(clone, "git", "config", "--unset", "core.hooksPath")
    (clone / "core" / "ring.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    r = sh(clone, "sh", "install.sh")
    assert r.returncode != 0 and "selftest" in (r.stdout + r.stderr).lower()


def test_install_with_an_old_python_fails(clone, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python3").write_text("#!/bin/sh\n[ \"$1\" = \"-c\" ] && exit 1\nexit 0\n", encoding="utf-8")
    (fake / "python3").chmod(0o755)
    r = sh(clone, "sh", "install.sh", env={"PATH": f"{fake}:{os.environ['PATH']}"})
    assert r.returncode != 0 and "3.10" in r.stdout + r.stderr


# ---- target (warns) and budget (blocks the commit that makes a loaded file bigger while over the ceiling) -------

LINKED = "---\narea: life\n---\n# A linked note\n\nBack to [[home]].\n"


def test_a_new_note_without_target_warns_and_the_commit_passes(clone):
    r = commit(clone, "vault/notes/life/n.md", LINKED)
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout + r.stderr
    assert "WARNING" in out and "notes/life/n.md" in out and "target: none" in out


def test_a_new_note_with_a_target_does_not_warn(clone):
    r = commit(clone, "vault/notes/life/n.md", LINKED.replace("area: life\n", "area: life\ntarget: none\n"))
    assert r.returncode == 0 and "WARNING" not in r.stdout + r.stderr


def test_an_edited_note_is_not_asked_for_a_target(clone):
    commit(clone, "vault/notes/life/n.md", LINKED)
    r = commit(clone, "vault/notes/life/n.md", LINKED + "\nmore text\n")
    assert r.returncode == 0 and "target" not in (r.stdout + r.stderr).replace("NOT_VERIFIED", "")


def test_target_block_in_gate_txt_blocks_the_commit(clone):
    (clone / "vault/gate.txt").write_text("orphan: block\ntarget: block\n", encoding="utf-8")
    r = commit(clone, "vault/notes/life/n.md", LINKED)
    out = r.stdout + r.stderr
    assert r.returncode == 1 and "COMMIT BLOCKED" in out and "no target" in out and "FAILS" in out


def test_a_malformed_target_mode_blocks_the_commit(clone):
    (clone / "vault/gate.txt").write_text("orphan: block\ntarget: maybe\n", encoding="utf-8")
    r = commit(clone, "vault/notes/life/n.md", LINKED)
    assert r.returncode == 1 and "maybe" in r.stdout + r.stderr


def test_growing_a_loaded_file_over_the_ceiling_blocks_the_commit(clone):
    r = commit(clone, "vault/CLAUDE.md", (clone / "vault/CLAUDE.md").read_text(encoding="utf-8") + "x" * 33_000)
    out = r.stdout + r.stderr
    assert r.returncode == 1 and "COMMIT BLOCKED" in out and "ceiling" in out and "tools/cool.py" in out


def test_a_commit_that_does_not_touch_the_loaded_files_passes_even_when_over(clone):
    big = (clone / "vault/CLAUDE.md").read_text(encoding="utf-8") + "x" * 33_000
    assert commit(clone, "vault/CLAUDE.md", big, "--no-verify").returncode == 0     # already over, committed on purpose
    r = commit(clone, "vault/notes/life/n.md", LINKED.replace("area: life\n", "area: life\ntarget: none\n"))
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_commit_that_shrinks_a_loaded_file_over_the_ceiling_passes(clone):
    big = (clone / "vault/CLAUDE.md").read_text(encoding="utf-8") + "x" * 40_000
    commit(clone, "vault/CLAUDE.md", big, "--no-verify")
    r = commit(clone, "vault/CLAUDE.md", big[:-5_000])
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("missing", ["target.py", "budget.py"])
def test_the_hook_without_a_new_check_is_an_incomplete_installation(clone, missing):
    (clone / "core" / missing).unlink()
    r = commit(clone, "docs/ok.txt", "clean\n")
    assert r.returncode == 1 and "install.sh" in r.stdout + r.stderr


def test_the_hook_leaves_its_edge_cache_inside_git_never_in_the_vault(clone):
    assert commit(clone, "vault/notes/life/n.md", LINKED.replace("area: life\n", "area: life\ntarget: none\n")).returncode == 0
    assert (clone / ".git" / "cogiforge-edges.json").is_file()
    assert not list((clone / "vault").rglob("cogiforge-edges.json"))
