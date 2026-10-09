"""ring.py edge cache: the pre-commit hook must not read every note again. It must also never be wrong: a stale
cache would call an orphan linked, or a linked note an orphan, and the gate would lie."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import ring
from helpers import vault

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "ring.py"
OLD = time.time() - 3600  # an hour ago: past the 2 s window in which a file is never cached


def age(v, when=OLD):
    for p in Path(v).rglob("*.md"):
        os.utime(p, (when, when))


def write_aged(v, rel, text, when=OLD):
    p = Path(v) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    os.utime(p, (when, when))


def run(v, cache=True):
    return ring.analyze(v, str(Path(v).parent / "cache.json") if cache else None)


@pytest.fixture
def v(tmp_path):
    root = tmp_path / "vault"
    vault(root, {"a.md": "goes to [[b]]\n", "b.md": "goes back to [[a]]\n", "loose.md": "no link\n"})
    age(root)
    return root


def test_the_cache_gives_the_same_answer_as_no_cache(v):
    assert run(v, cache=False) == run(v) == run(v)


def test_a_cache_is_written_for_files_that_are_old_enough(v):
    run(v)
    data = json.loads((v.parent / "cache.json").read_text(encoding="utf-8"))
    assert data["version"] == ring.CACHE_VERSION
    assert sorted(data["notes"]) == ["a.md", "b.md", "loose.md"]
    assert data["notes"]["a.md"][2] == ["b"]


def test_a_second_and_a_third_run_do_not_read_the_notes_again(v, monkeypatch):
    run(v)
    run(v)                                   # a hit has to keep the entry alive for the run after it
    monkeypatch.setattr(ring, "link_targets", lambda *a: (_ for _ in ()).throw(AssertionError("read a cached note")))
    notes, degree = run(v)
    assert ring.chk_orphans(notes, degree) == ["loose.md"]


def test_a_changed_size_is_read_again(v):
    run(v)
    write_aged(v, "loose.md", "now it links to [[a]] and is no longer an orphan\n")
    notes, degree = run(v)
    assert ring.chk_orphans(notes, degree) == []


def test_a_changed_mtime_with_the_same_size_is_read_again(v):
    write_aged(v, "x.md", "link to [[a]]\n")          # 14 bytes
    run(v)
    write_aged(v, "x.md", "link to [[q]]\n", when=OLD - 500)   # same size, other mtime, a dead link now
    notes, degree = run(v)
    assert degree["x.md"] == 0 and degree["a.md"] == 2


def test_a_changed_size_with_the_same_mtime_is_read_again(v):
    write_aged(v, "x.md", "to [[a]]\n")
    run(v)
    write_aged(v, "x.md", "to [[q]] and more words\n")  # same mtime, other size
    notes, degree = run(v)
    assert degree["x.md"] == 0


def test_a_file_changed_a_moment_ago_is_never_cached(v):
    (v / "fresh.md").write_text("to [[a]]\n", encoding="utf-8")   # mtime = now
    run(v)
    assert "fresh.md" not in json.loads((v.parent / "cache.json").read_text())["notes"]


def test_a_deleted_note_leaves_the_cache(v):
    run(v)
    (v / "loose.md").unlink()
    run(v)
    assert "loose.md" not in json.loads((v.parent / "cache.json").read_text())["notes"]


def test_a_new_note_that_a_cached_link_name_now_resolves_to_is_seen(v):
    """The cache keeps the raw link text, not where it pointed: creating the target later has to count."""
    write_aged(v, "x.md", "to [[later]]\n")
    notes, degree = run(v)
    assert degree["x.md"] == 0
    write_aged(v, "later.md", "arrived\n")
    notes, degree = run(v)
    assert degree["x.md"] == 1 and degree["later.md"] == 1


@pytest.mark.parametrize("junk", ["not json at all", "[]", "{}", '{"version": 1}', '{"version": 1, "notes": 5}',
                                  '{"version": 1, "notes": {"a.md": "junk", "b.md": [1, 2]}}'])
def test_a_corrupt_cache_is_ignored_and_rewritten(v, junk):
    (v.parent / "cache.json").write_text(junk, encoding="utf-8")
    notes, degree = run(v)
    assert ring.chk_orphans(notes, degree) == ["loose.md"]
    assert sorted(json.loads((v.parent / "cache.json").read_text())["notes"]) == ["a.md", "b.md", "loose.md"]


def test_a_cache_from_another_version_is_not_trusted(v):
    (v.parent / "cache.json").write_text(json.dumps({"version": 0, "notes": {
        "loose.md": [(v / "loose.md").stat().st_size, (v / "loose.md").stat().st_mtime_ns, ["a"]]}}), encoding="utf-8")
    notes, degree = run(v)
    assert ring.chk_orphans(notes, degree) == ["loose.md"]


def test_a_cache_that_cannot_be_written_does_not_stop_the_gate(v):
    (v.parent / "cache.json").mkdir()   # a directory where the file should go
    notes, degree = run(v)
    assert ring.chk_orphans(notes, degree) == ["loose.md"]


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


def test_git_cache_file_is_inside_the_git_dir_never_in_the_vault(tmp_path):
    git(tmp_path, "init", "-q")
    vault(tmp_path / "vault", {"a.md": "x\n"})
    f = ring.git_cache_file(tmp_path / "vault")
    assert Path(f).parent == (tmp_path / ".git").resolve() and Path(f).name == "cogiforge-edges.json"


def test_no_cache_file_outside_a_git_repo(tmp_path):
    vault(tmp_path / "vault", {"a.md": "x\n"})
    assert ring.git_cache_file(tmp_path / "vault") is None


def test_gate_stage_writes_the_cache_in_git_and_the_plain_gate_does_not(tmp_path):
    git(tmp_path, "init", "-q")
    v = vault(tmp_path / "vault", {"a.md": "goes [[b]]\n", "b.md": "goes [[a]]\n"})
    age(v)
    git(tmp_path, "add", "-A")
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--gate"], capture_output=True, text=True)
    assert r.returncode == 0 and not (tmp_path / ".git" / "cogiforge-edges.json").exists()
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--gate", "--stage"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert (tmp_path / ".git" / "cogiforge-edges.json").is_file()
    assert sorted(p.name for p in v.iterdir()) == ["a.md", "b.md"]   # nothing was added to the vault


def test_a_stale_cache_never_hides_an_orphan_in_the_commit(tmp_path):
    """The whole point: cached at one state, edited, the commit must be judged on the new state."""
    git(tmp_path, "init", "-q")
    v = vault(tmp_path / "vault", {"a.md": "goes [[b]]\n", "b.md": "goes [[a]]\n", "n.md": "goes [[a]]\n"})
    age(v)
    git(tmp_path, "add", "-A")
    cmd = [sys.executable, str(SCRIPT), "--vault", str(v), "--gate", "--stage"]
    assert subprocess.run(cmd, capture_output=True, text=True).returncode == 0
    write_aged(v, "n.md", "orphan now\n", when=OLD + 7)
    write_aged(v, "a.md", "goes [[b]]\n", when=OLD)           # a no longer links n, a is untouched in size
    git(tmp_path, "add", "-A")
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 1 and "n.md" in r.stdout


def test_gate_txt_may_carry_a_target_line_without_the_ring_rejecting_it(tmp_path):
    v = vault(tmp_path, {"a.md": "goes [[b]]\n", "b.md": "goes [[a]]\n", "gate.txt": "orphan: block\ntarget: warn\n"})
    assert subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--gate"], capture_output=True).returncode == 0
