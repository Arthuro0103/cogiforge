"""Updating a workbench with plain git: the two command blocks of the README ("Updating your workbench"), run for real.

Everything is local (no network): a fake upstream with three tags, and `url.<path>.insteadOf` to send the GitHub
URL of the README to it. The blocks are read from README.md, never copied here, so changing them breaks the test.
"""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB = "https://github.com/Arthuro0103/cogiforge.git"


def readme_blocks():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    sec = re.search(r"^## Updating your workbench\n(.*?)(?=^## )", text, re.S | re.M).group(1)
    blocks = re.findall(r"^```sh\n(.*?)\n```", sec, re.S | re.M)
    assert len(blocks) == 2, blocks
    return blocks   # [normal block, one-time block for a workbench made before]


def env_for(tmp_path, upstream):
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e.update(HOME=str(tmp_path / "home"), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
             GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
             GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0=f"url.{upstream}.insteadOf", GIT_CONFIG_VALUE_0=GITHUB,
             GIT_CONFIG_KEY_1="protocol.file.allow", GIT_CONFIG_VALUE_1="always")
    (tmp_path / "home").mkdir(exist_ok=True)
    return e


def git(cwd, env, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if check:
        assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r


def sh(cwd, env, cmd):
    return subprocess.run(["sh", "-c", cmd], cwd=cwd, env=env, capture_output=True, text=True)


X0 = "line1\nline2 original\nline3\nline4\n"
X2 = "line1\nline2 NEW IN 0.1.2\nline3\nline4\n"


def make_upstream(tmp_path):
    up = tmp_path / "upstream"
    up.mkdir()
    e = env_for(tmp_path, up)
    git(up, e, "init", "-q", "-b", "main")

    def commit(files, msg, tag):
        for name, body in files.items():
            p = up / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        git(up, e, "add", "-A")
        git(up, e, "commit", "-qm", msg)
        git(up, e, "tag", tag)
        return git(up, e, "rev-parse", "HEAD").stdout.strip()

    commit({"core/x.py": X0, "CLAUDE.md": "rules\nmine to edit\n", "vault/home.md": "home\n"}, "0.1.0", "v0.1.0")
    sha1 = commit({"vault/home.md": "home v2\n"}, "0.1.1", "v0.1.1")
    commit({".claude/skills/cf-new/SKILL.md": "new skill\n", "core/x.py": X2}, "0.1.2", "v0.1.2")
    git(up, e, "checkout", "-q", "v0.1.1")   # a normal repo with HEAD away from the newest tag: only tags matter
    return up, e, sha1


def new_way(tmp_path, up, e, sha1):
    """How the new skill builds a workbench: fetch the pinned hash, keep the history, add the remote."""
    wb = tmp_path / "wb"
    git(tmp_path, e, "init", "-q", str(wb))
    git(wb, e, "fetch", "-q", "--depth", "1", GITHUB, sha1)
    git(wb, e, "-c", "advice.detachedHead=false", "checkout", "-q", "-B", "main", "FETCH_HEAD")
    assert git(wb, e, "rev-parse", "HEAD").stdout.strip() == sha1
    git(wb, e, "remote", "add", "cogiforge", GITHUB)
    git(wb, e, "commit", "--allow-empty", "-qm", "workbench from cogiforge 0.1.1")
    return wb


def old_way(tmp_path, up, e, sha1):
    """How the old skill built it: fetch the hash, throw the .git away, start a new history."""
    wb = tmp_path / "wb"
    git(tmp_path, e, "init", "-q", str(wb))
    git(wb, e, "fetch", "-q", "--depth", "1", GITHUB, sha1)
    git(wb, e, "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD")
    subprocess.run(["rm", "-rf", str(wb / ".git")], check=True)
    git(wb, e, "init", "-q", "-b", "main")
    git(wb, e, "add", "-A")
    git(wb, e, "commit", "-qm", "workbench from cogiforge 0.1.1")
    return wb


def person_works(wb, e):
    (wb / "CLAUDE.md").write_text("rules\nmine edited by the person\n", encoding="utf-8")
    (wb / "vault" / "my-note.md").write_text("my note\n", encoding="utf-8")
    git(wb, e, "add", "-A")
    git(wb, e, "commit", "-qm", "my work")


def check_updated(wb):
    assert (wb / ".claude/skills/cf-new/SKILL.md").read_text() == "new skill\n"
    assert "NEW IN 0.1.2" in (wb / "core/x.py").read_text()
    assert (wb / "CLAUDE.md").read_text() == "rules\nmine edited by the person\n"
    assert (wb / "vault/my-note.md").read_text() == "my note\n"


def test_new_way_workbench_updates_with_the_normal_block(tmp_path):
    normal, _ = readme_blocks()
    up, e, sha1 = make_upstream(tmp_path)
    wb = new_way(tmp_path, up, e, sha1)
    person_works(wb, e)
    r = sh(wb, e, normal)
    assert r.returncode == 0, (r.stdout, r.stderr)
    check_updated(wb)
    assert "cogiforge" in git(wb, e, "remote", "-v").stdout


def test_old_way_workbench_connects_once_then_updates(tmp_path):
    normal, once = readme_blocks()
    up, e, sha1 = make_upstream(tmp_path)
    wb = old_way(tmp_path, up, e, sha1)
    assert git(wb, e, "log", "--reverse", "--format=%s").stdout.splitlines()[0] == "workbench from cogiforge 0.1.1"
    person_works(wb, e)
    before = {p: (wb / p).read_text() for p in ("CLAUDE.md", "core/x.py", "vault/my-note.md")}
    r = sh(wb, e, once.replace("0.1.X", "0.1.1"))
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert {p: (wb / p).read_text() for p in before} == before   # the one-time step changes no file
    r = sh(wb, e, normal)
    assert r.returncode == 0, (r.stdout, r.stderr)
    check_updated(wb)
    assert "<<<<<<<" not in (wb / "core/x.py").read_text()


def test_conflict_stops_lists_the_file_and_loses_nothing(tmp_path):
    normal, _ = readme_blocks()
    up, e, sha1 = make_upstream(tmp_path)
    wb = new_way(tmp_path, up, e, sha1)
    (wb / "core/x.py").write_text("line1\nline2 CHANGED BY THE PERSON\nline3\nline4\n", encoding="utf-8")
    git(wb, e, "add", "-A")
    git(wb, e, "commit", "-qm", "person edits x.py")
    mine = git(wb, e, "rev-parse", "HEAD").stdout.strip()
    r = sh(wb, e, normal)
    assert r.returncode != 0
    assert "core/x.py" in r.stdout + r.stderr
    body = (wb / "core/x.py").read_text()
    assert "<<<<<<<" in body and "CHANGED BY THE PERSON" in body and "NEW IN 0.1.2" in body
    assert git(wb, e, "merge-base", "--is-ancestor", mine, "HEAD").returncode == 0   # her commit is still in history
