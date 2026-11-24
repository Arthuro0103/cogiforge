"""Paired tests for stale.py: each signal finds, the clean case does not, the threshold is exact, and git is optional."""
import json
import os
import subprocess
import sys
from pathlib import Path

STALE = str(Path(__file__).with_name("stale.py"))
HEAD = 'Format of each line:\n'
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *args, date="2026-06-01T12:00:00"):
    env = {**GIT_ENV, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env, check=True)


def repo(tmp_path, memory_lines, git_on=True):
    v = tmp_path / "vault"
    (v / "memory").mkdir(parents=True)
    (v / "docs").mkdir()
    (v / "docs" / "plan.md").write_text("v0\n", encoding="utf-8")
    (v / "memory" / "profile.md").write_text("# Profile\n\n" + HEAD + "\n".join(memory_lines) + "\n", encoding="utf-8")
    if git_on:
        git(tmp_path, "init", "-q")
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "-q", "-m", "init", date="2026-01-01T12:00:00")
    return v


def edit(v, tmp_path, n, first=2):
    """n commits touching docs/plan.md, all in June 2026."""
    for i in range(n):
        (v / "docs" / "plan.md").write_text(f"v{first + i}\n", encoding="utf-8")
        git(tmp_path, "commit", "-q", "-am", f"c{i}", date=f"2026-06-0{i + 1}T12:00:00")


def run(v, *args, tmp_path=None):
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(v.parent.parent)} if tmp_path is None else os.environ
    return subprocess.run([sys.executable, STALE, "--vault", str(v), "--root", str(v.parent), "--today", "2026-10-08", *args],
                          capture_output=True, text=True, env=env)


def entry(phrase, where="chat", extra=""):
    return f'2026-02-01 | "{phrase}" | {where}{extra}'


def signals(r):
    return [l.split()[1] for l in r.stdout.splitlines() if len(l.split()) > 1 and l.split()[1] in
            ("dead-path", "moved", "aged", "expired", "superseded")]


def test_a_clean_memory_has_no_finding(tmp_path):
    v = repo(tmp_path, [entry("the plan lives in `docs/plan.md` and is short")])
    r = run(v, "--gate")
    assert r.returncode == 0 and signals(r) == [] and "0 finding(s)" in r.stdout


def test_dead_path(tmp_path):
    v = repo(tmp_path, [entry("it is in `docs/gone.md` now")])
    r = run(v)
    assert signals(r) == ["dead-path"] and "docs/gone.md" in r.stdout and r.returncode == 0


def test_moved_shows_the_new_path(tmp_path):
    v = repo(tmp_path, [entry("it is in [[old/plan.md|the plan]]")])
    r = run(v)
    assert signals(r) == ["moved"] and "docs/plan.md" in r.stdout


def test_a_line_suffix_is_dropped(tmp_path):
    v = repo(tmp_path, [entry("see `docs/plan.md:12` for it")])
    assert signals(run(v)) == []
    v2 = repo(tmp_path / "b", [entry("see `docs/gone.md:12-14` there")])
    r = run(v2)
    assert signals(r) == ["dead-path"] and "`docs/gone.md`" in r.stdout


def test_aged_needs_the_threshold_exactly(tmp_path):
    v = repo(tmp_path, [entry("the plan is in `docs/plan.md`")])
    edit(v, tmp_path, 3)                                          # 3 commits after the entry date
    r = run(v)
    assert signals(r) == ["aged"] and "3 commits" in r.stdout
    assert signals(run(v, "--threshold", "4")) == []


def test_two_commits_are_below_the_threshold(tmp_path):
    v = repo(tmp_path, [entry("the plan is in `docs/plan.md`")])
    edit(v, tmp_path, 2)
    assert signals(run(v)) == []


def test_a_commit_before_the_entry_date_does_not_count(tmp_path):
    v = repo(tmp_path, ['2026-07-01 | "the plan is in `docs/plan.md`" | chat'])
    edit(v, tmp_path, 3)                                          # all in June, before 2026-07-01
    assert signals(run(v)) == []


def test_a_commit_on_the_entry_day_does_not_count(tmp_path):
    v = repo(tmp_path, ['2026-06-01 | "the plan is in `docs/plan.md`" | chat'])
    edit(v, tmp_path, 3)                                          # June 1, 2 and 3: only 2 are after the entry day
    assert signals(run(v)) == []


def test_a_folder_does_not_age(tmp_path):
    v = repo(tmp_path, [entry("the plans are in [[docs/plan.md]] and the folder `docs/`")])
    edit(v, tmp_path, 3)
    assert signals(run(v)) == ["aged"]                            # only the file: the folder is not a cited file


def test_expired_by_stale_after(tmp_path):
    v = repo(tmp_path, [entry("a fact", extra=" | stale_after: 2026-09-01"), entry("another", extra=" | stale_after: 2026-12-01")])
    r = run(v)
    assert signals(r) == ["expired"] and "profile.md:" in r.stdout


def test_today_is_read_from_the_flag(tmp_path):
    v = repo(tmp_path, [entry("a fact", extra=" | stale_after: 2026-09-01")])
    r = subprocess.run([sys.executable, STALE, "--vault", str(v), "--root", str(v.parent), "--today", "2026-08-01"], capture_output=True, text=True)
    assert signals(r) == []


def test_a_note_with_stale_after_expires(tmp_path):
    v = repo(tmp_path, [entry("a fact")])
    (v / "notes").mkdir()
    (v / "notes" / "old.md").write_text("---\narea: life\nstale_after: 2026-05-05\n---\n# Old\n", encoding="utf-8")
    (v / "notes" / "fresh.md").write_text("---\nstale_after: 2027-05-05\n---\n# Fresh\n", encoding="utf-8")
    r = run(v)
    assert signals(r) == ["expired"] and "old.md" in r.stdout and "fresh.md" not in r.stdout


def test_superseded_only_in_a_loaded_file(tmp_path):
    v = repo(tmp_path, [entry("old rule", extra=" | superseded_by: 2026-09-09")])
    (v / "memory" / "archive").mkdir()
    (v / "memory" / "archive" / "profile.md").write_text(HEAD + entry("older", extra=" | superseded_by: 2026-03-03") + "\n", encoding="utf-8")
    r = run(v)
    assert signals(r) == ["superseded"] and "archive" not in r.stdout


def test_team_mode_memory_is_scanned(tmp_path):
    v = repo(tmp_path, [entry("a fact")])
    (v / "people" / "ana" / "memory").mkdir(parents=True)
    (v / "people" / "ana" / "memory" / "profile.md").write_text(HEAD + entry("see `docs/gone.md`") + "\n", encoding="utf-8")
    r = run(v)
    assert signals(r) == ["dead-path"] and "people/ana/memory/profile.md" in r.stdout


def test_gate_fails_on_a_finding_and_passes_on_clean(tmp_path):
    v = repo(tmp_path, [entry("it is in `docs/gone.md` now")])
    assert run(v, "--gate").returncode == 1 and run(v).returncode == 0
    clean = repo(tmp_path / "c", [entry("fine")])
    assert run(clean, "--gate").returncode == 0


def test_without_git_the_other_signals_run_and_aged_is_not_verified(tmp_path):
    v = repo(tmp_path, [entry("see `docs/gone.md` and `docs/plan.md`")], git_on=False)
    r = run(v, "--gate")
    assert r.returncode == 1 and signals(r) == ["dead-path"]
    assert "NOT_VERIFIED: no git repository" in r.stdout and "aged" in r.stdout
    assert run(v).returncode == 3


def test_an_unreadable_file_is_not_verified(tmp_path):
    v = repo(tmp_path, [entry("a fact")])
    (v / "memory" / "decisions.md").write_bytes(b"\xff\xfe\x00bad")
    r = run(v)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout and "decisions.md" in r.stdout


def test_json_has_counts(tmp_path):
    v = repo(tmp_path, [entry("it is in `docs/gone.md` now")])
    d = json.loads(run(v, "--json").stdout)
    assert d["counts"]["dead-path"] == 1 and d["findings"][0]["signal"] == "dead-path"


def test_the_entry_cited_path_in_where_counts(tmp_path):
    v = repo(tmp_path, [entry("a fact", where="`docs/gone.md`")])
    assert signals(run(v)) == ["dead-path"]
