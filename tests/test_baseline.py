"""The old debt in .cogiforge/baseline.json (issue #2): the hook that tools/adopt.py installs lets it through, and still
blocks anything new. Real commits in a temporary vault, real hook, no network."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADOPT = ROOT / "tools" / "adopt.py"
LEAK = ROOT / "core" / "leak.py"
GATE = ROOT / "core" / "gate.py"
PHONE = "11 98765" + "-4321"  # assembled here so this file does not accuse itself
PHONE_NOTE = f"ideas/ligar {PHONE}.md"  # a note NAMED with a phone: its name goes into the baseline


def env(tmp_path):
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LEAK_BLOCKLIST": str(tmp_path / "absent.txt"),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def write(v, rel, text):
    p = Path(v) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def git(v, *a, tmp):
    return subprocess.run(["git", "-C", str(v), *a], capture_output=True, text=True, env=env(tmp), stdin=subprocess.DEVNULL)


def adopted(tmp_path, files, history=None):
    """A vault with `files`, git init and NO commit, adopted (dry run, then --apply --confirm). `history`: a file
    committed before the adopt, so HEAD exists and has no baseline."""
    v = tmp_path / "vault"
    for rel, text in files.items():
        write(v, rel, text)
    subprocess.run(["git", "init", "-q"], cwd=v, check=True)
    if history:
        write(v, history, "linked to [[reading]]\n")
        git(v, "add", history, tmp=tmp_path)
        assert git(v, "commit", "-q", "-m", "before", tmp=tmp_path).returncode == 0
    run = lambda *a: subprocess.run([sys.executable, str(ADOPT), str(v), *a], capture_output=True, text=True,
                                    env=env(tmp_path), stdin=subprocess.DEVNULL)
    sha = re.search(r"plan-sha256: ([0-9a-f]{64})", run().stdout).group(1)
    r = run("--apply", "--confirm", sha)
    assert r.returncode == 0, r.stdout + r.stderr
    return v


def commit(v, tmp, *paths, all_=False):
    git(v, "add", *(["-A"] if all_ else paths), tmp=tmp)
    return git(v, "commit", "-q", "-m", "x", tmp=tmp)


def out(r):
    return r.stdout + r.stderr


BASE = {
    "reading.md": "reading notes\n",
    "ideas/loose-idea.md": "a loose idea\n",
    PHONE_NOTE: "see [[reading]]\n",
}


def test_the_first_commit_after_adopt_passes(tmp_path):
    v = adopted(tmp_path, BASE)
    r = commit(v, tmp_path, all_=True)
    assert r.returncode == 0, out(r)
    assert git(v, "rev-list", "--count", "HEAD", tmp=tmp_path).stdout.strip() == "1"


def test_a_new_orphan_in_the_first_commit_still_blocks(tmp_path):
    v = adopted(tmp_path, BASE)
    write(v, "ideas/new-loose.md", "brand new, no link\n")
    r = commit(v, tmp_path, all_=True)
    assert r.returncode != 0
    fails = out(r).split("FAILS", 1)[1]
    assert "ideas/new-loose.md" in fails and "ideas/loose-idea.md" not in fails


def test_editing_the_old_orphan_later_passes(tmp_path):
    v = adopted(tmp_path, BASE)
    assert commit(v, tmp_path, all_=True).returncode == 0
    write(v, "ideas/loose-idea.md", "a loose idea, edited\n")
    r = commit(v, tmp_path, "ideas/loose-idea.md")
    assert r.returncode == 0, out(r)


def test_a_commit_that_adds_a_note_to_the_baseline_does_not_exempt_it(tmp_path):
    v = adopted(tmp_path, BASE)
    assert commit(v, tmp_path, all_=True).returncode == 0
    write(v, "ideas/sneaky.md", "no link\n")
    b = v / ".cogiforge" / "baseline.json"
    data = json.loads(b.read_text())
    data["orphans"].append("ideas/sneaky.md")
    b.write_text(json.dumps(data))
    r = commit(v, tmp_path, "ideas/sneaky.md", ".cogiforge/baseline.json")
    assert r.returncode != 0 and "ideas/sneaky.md" in out(r)
    assert git(v, "rev-list", "--count", "HEAD", tmp=tmp_path).stdout.strip() == "1"


def test_a_baseline_that_is_not_in_the_commit_exempts_nothing(tmp_path):
    v = adopted(tmp_path, BASE)
    r = commit(v, tmp_path, "reading.md", "ideas/loose-idea.md")  # the baseline stays untracked
    assert r.returncode != 0 and "ideas/loose-idea.md" in out(r)


def test_a_baseline_that_head_does_not_have_exempts_nothing(tmp_path):
    v = adopted(tmp_path, BASE, history="before.md")  # HEAD exists, and has no baseline
    r = commit(v, tmp_path, all_=True)
    assert r.returncode != 0 and "ideas/loose-idea.md" in out(r)


def test_deleting_the_baseline_in_the_commit_exempts_nothing(tmp_path):
    v = adopted(tmp_path, BASE)
    assert commit(v, tmp_path, all_=True).returncode == 0
    git(v, "rm", "-q", "--cached", ".cogiforge/baseline.json", tmp=tmp_path)
    write(v, "ideas/loose-idea.md", "edited\n")
    r = commit(v, tmp_path, "ideas/loose-idea.md")
    assert r.returncode != 0 and "ideas/loose-idea.md" in out(r)


DEAD = {
    "a.md": "see [[b]] and [[ghost]]\n",
    "b.md": "back to [[a]]\n",
}


def test_an_old_dead_link_passes_even_when_lines_move_and_a_new_one_blocks(tmp_path):
    v = adopted(tmp_path, DEAD)
    assert commit(v, tmp_path, all_=True).returncode == 0
    write(v, "a.md", "a new first line\n\nsee [[b]] and [[ghost]]\n")  # the old dead link moved to line 3
    r = commit(v, tmp_path, "a.md")
    assert r.returncode == 0, out(r)
    write(v, "a.md", "see [[b]] and [[ghost]] and [[phantom]]\n")  # a NEW dead link inside an OLD note
    r = commit(v, tmp_path, "a.md")
    assert r.returncode != 0 and "phantom" in out(r) and "ghost]] does not" not in out(r)


def test_the_same_dead_target_again_is_new_debt(tmp_path):
    v = adopted(tmp_path, DEAD)
    assert commit(v, tmp_path, all_=True).returncode == 0
    write(v, "a.md", "see [[b]] and [[ghost]] and again [[ghost]]\n")  # the baseline counted it once
    r = commit(v, tmp_path, "a.md")
    assert r.returncode != 0 and "ghost" in out(r)


def test_a_commit_that_adds_a_dead_link_to_the_baseline_does_not_exempt_it(tmp_path):
    v = adopted(tmp_path, DEAD)
    assert commit(v, tmp_path, all_=True).returncode == 0
    b = v / ".cogiforge" / "baseline.json"
    data = json.loads(b.read_text())
    data["dead_links"].append("a.md:1 [[phantom]]")
    b.write_text(json.dumps(data))
    write(v, "a.md", "see [[b]] and [[ghost]] and [[phantom]]\n")
    r = commit(v, tmp_path, "a.md", ".cogiforge/baseline.json")
    assert r.returncode != 0 and "phantom" in out(r)


def test_a_dead_link_in_a_note_that_the_baseline_does_not_list_blocks(tmp_path):
    v = adopted(tmp_path, DEAD)
    assert commit(v, tmp_path, all_=True).returncode == 0
    write(v, "b.md", "back to [[a]] and [[ghost]]\n")  # `ghost` is old debt of a.md, not of b.md
    r = commit(v, tmp_path, "b.md")
    assert r.returncode != 0 and "b.md" in out(r)


# ---- the gate on its own: area and frontmatter, with a hand-written baseline on the disk (no git) ----------------------

def gate_vault(tmp_path, baseline):
    v = tmp_path / "gv"
    write(v, "areas.txt", "life: life\n")
    write(v, "notes/life/no-area.md", "---\ntitle: x\n---\nbody\n")
    write(v, "notes/life/wrong-area.md", "---\narea: other\n---\nbody\n")
    write(v, "notes/life/bad-fm.md", "---\narea: life\nkey: [unclosed\n---\nbody\n")
    if baseline is not None:
        write(v, ".cogiforge/baseline.json", json.dumps(baseline))
    return v


def run_gate(v, *files):
    r = subprocess.run([sys.executable, str(GATE), "--vault", str(v), *files], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout


ALL = ["notes/life/no-area.md", "notes/life/wrong-area.md", "notes/life/bad-fm.md"]


def test_gate_without_a_baseline_fails_all_three(tmp_path):
    rc, text = run_gate(gate_vault(tmp_path, None), *ALL)
    assert rc == 1 and "no-area.md" in text and "wrong-area.md" in text and "bad-fm.md" in text


def test_gate_lets_the_listed_area_and_frontmatter_debt_through(tmp_path):
    v = gate_vault(tmp_path, {"area_missing": ["notes/life/no-area.md"], "frontmatter_errors": ["notes/life/bad-fm.md"]})
    rc, text = run_gate(v, *ALL)
    assert rc == 1 and "wrong-area.md" in text  # a different area failure is not what the baseline lists
    assert "no-area.md ::" not in text and "bad-fm.md ::" not in text
    assert "2 old failure(s) hidden" in text
    assert run_gate(v, ALL[0], ALL[2])[0] == 0


def test_a_listed_note_with_a_different_area_failure_still_fails(tmp_path):
    v = gate_vault(tmp_path, {"area_missing": ["notes/life/wrong-area.md"]})  # it HAS an area now, and a wrong one
    rc, text = run_gate(v, "notes/life/wrong-area.md")
    assert rc == 1 and "wrong-area.md" in text


def test_gate_without_files_is_a_full_audit_and_hides_nothing(tmp_path):
    v = gate_vault(tmp_path, {"area_missing": ["notes/life/no-area.md"], "frontmatter_errors": ["notes/life/bad-fm.md"]})
    rc, text = run_gate(v)
    assert rc == 1 and "no-area.md" in text and "bad-fm.md" in text


def test_a_malformed_baseline_exempts_nothing(tmp_path):
    v = gate_vault(tmp_path, None)
    write(v, ".cogiforge/baseline.json", '{"area_missing": "not a list"')
    rc, text = run_gate(v, *ALL)
    assert rc == 1 and "no-area.md" in text


# ---- leak.py ---------------------------------------------------------------------------------------------------------

def run_leak(cwd, *args, tmp):
    return subprocess.run([sys.executable, str(LEAK), *args], cwd=cwd, capture_output=True, text=True, env=env(tmp),
                          stdin=subprocess.DEVNULL)


def test_leak_skips_exactly_the_baseline_in_both_modes(tmp_path):
    v = tmp_path / "lv"
    write(v, ".cogiforge/baseline.json", json.dumps({"area_missing": [PHONE_NOTE]}))
    write(v, "ok.md", "clean\n")
    subprocess.run(["git", "init", "-q"], cwd=v, check=True)
    git(v, "add", "-A", tmp=tmp_path)
    r = run_leak(v, "--staged", tmp=tmp_path)
    assert r.returncode == 0, out(r)
    r = run_leak(v, tmp=tmp_path)
    assert r.returncode == 0, out(r)
    r = run_leak(tmp_path, "lv", tmp=tmp_path)  # given as a folder from outside
    assert r.returncode == 0, out(r)


def test_leak_still_reads_everything_else(tmp_path):
    v = tmp_path / "lv"
    write(v, ".cogiforge/baseline.json", json.dumps({"area_missing": [PHONE_NOTE]}))
    write(v, ".cogiforge/other.json", json.dumps({"x": f"ring {PHONE}"}))
    write(v, ".cogiforge/baseline.json.bak", json.dumps({"x": f"ring {PHONE}"}))
    write(v, "sub/.cogiforge/baseline.json", json.dumps({"x": f"ring {PHONE}"}))
    write(v, "note.md", f"call {PHONE} now\n")
    subprocess.run(["git", "init", "-q"], cwd=v, check=True)
    git(v, "add", "-A", tmp=tmp_path)
    for args in (("--staged",), ()):
        r = run_leak(v, *args, tmp=tmp_path)
        assert r.returncode == 1, out(r)
        for name in ("note.md:1: phone", ".cogiforge/other.json:1: phone", ".cogiforge/baseline.json.bak:1: phone",
                     "sub/.cogiforge/baseline.json:1: phone"):
            assert name in r.stdout, (args, r.stdout)
        assert "\n.cogiforge/baseline.json:" not in "\n" + r.stdout
