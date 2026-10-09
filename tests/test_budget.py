"""budget.py: what a session loads, a ceiling on it, and a hook that only blocks the commit that makes it worse."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import budget

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "budget.py"


def put(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def blob(n):
    return "x" * n


def skill(root, name, desc):
    put(root, f".claude/skills/{name}/SKILL.md", f"---\nname: {name}\ndescription: {desc}\n---\n\n# body that does not count\n" + blob(500))


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--vault", str(Path(root) / "vault"), "--root", str(root), *args],
                          capture_output=True, text=True)


def measure(root):
    return budget.measure(Path(root) / "vault", Path(root))


@pytest.fixture
def root(tmp_path):
    put(tmp_path, "CLAUDE.md", blob(1000))
    put(tmp_path, "vault/CLAUDE.md", blob(2000))
    for name, n in (("profile", 100), ("patterns", 200), ("decisions", 300)):
        put(tmp_path, f"vault/memory/{name}.md", blob(n))
    return tmp_path


def test_every_session_is_the_sum_of_the_loaded_files_and_the_skill_descriptions(root):
    skill(root, "one", "a" * 40)
    skill(root, "two", "b" * 60)
    m = measure(root)
    assert m["skill_descriptions"] == 100          # only the description: the body of the skill is not loaded up front
    assert m["always"] == 1000 + 2000 + 100 + 200 + 300 + 100


def test_a_missing_loaded_file_counts_as_zero_and_is_listed_as_missing(root):
    (root / "vault/memory/patterns.md").unlink()
    m = measure(root)
    assert m["always"] == 1000 + 2000 + 100 + 300 and None in m["files"].values()
    assert "missing" in run(root).stdout


def test_within_the_ceiling_is_rc_0(root):
    r = run(root)
    assert r.returncode == 0 and "EVERY SESSION" in r.stdout and "OVER" not in r.stdout


def test_the_ceiling_is_inclusive_and_one_byte_more_fails(tmp_path):
    put(tmp_path, "CLAUDE.md", blob(budget.ALWAYS_MAX))
    (tmp_path / "vault").mkdir()
    assert run(tmp_path).returncode == 0
    put(tmp_path, "CLAUDE.md", blob(budget.ALWAYS_MAX + 1))
    r = run(tmp_path)
    assert r.returncode == 1 and "OVER" in r.stdout and "every session" in r.stdout


def test_over_the_ceiling_teaches_the_fix(root):
    put(root, "vault/memory/decisions.md", blob(budget.ALWAYS_MAX))
    r = run(root)
    assert r.returncode == 1
    for hint in ("How to fix", "tools/cool.py", "--no-verify"):
        assert hint in r.stdout


def test_opening_the_worst_project_is_measured_and_has_its_own_ceiling(root):
    put(root, "vault/projects/small/instructions.md", blob(500))
    put(root, "vault/projects/zeta-big/instructions.md", blob(budget.OPEN_MAX))
    m = measure(root)
    assert m["worst_project"] == "zeta-big"          # not the first by name, the biggest
    r = run(root)
    assert r.returncode == 1 and "opening 'zeta-big'" in r.stdout and "every session loads" not in r.stdout


def test_a_project_folder_without_a_root_is_not_a_project(root):
    put(root, "vault/projects/loose/notes.md", blob(60000))
    assert measure(root)["projects"] == 0 and run(root).returncode == 0


def test_only_the_three_newest_diary_entries_load(root):
    for d in ("2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"):
        put(root, f"vault/memory/diary/{d}.md", blob(1000 if d == "2026-01-01" else 10))
    put(root, "vault/projects/p/instructions.md", "x")
    assert measure(root)["diary"] == 30              # the 1000-byte oldest one is left out


def _task(root, name, status, project="p"):
    put(root, f"vault/tasks/{name}.md", f"---\ntags:\n  - task\nstatus: {status}\nprojects:\n  - \"[[projects/{project}/instructions|{project}]]\"\n---\n" + blob(100))


def test_only_open_tasks_of_this_project_count_and_at_most_five(root):
    put(root, "vault/projects/p/instructions.md", "x")
    put(root, "vault/projects/q/instructions.md", "x")
    for i in range(8):
        _task(root, f"open{i}", "open")
    _task(root, "zdoing", "in-progress")   # sorts last, so the five that load are open0..open4
    _task(root, "finished", "done")
    _task(root, "elsewhere", "open", project="q")
    w = measure(root)
    assert w["worst_project"] == "p"
    one = len((root / "vault/tasks/open0.md").read_bytes())
    assert w["worst"]["tasks"] == 5 * one


def test_nothing_readable_is_not_verified_never_ok(tmp_path):
    (tmp_path / "vault").mkdir()
    r = run(tmp_path)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout and "OK" not in r.stdout


def test_a_missing_vault_is_not_verified(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(tmp_path / "none")], capture_output=True, text=True)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_json_carries_the_numbers_and_the_verdict(root):
    data = json.loads(run(root, "--json").stdout)
    assert data["always"] == 3600 and data["over"] == [] and data["projects"] == 0


# ---- --staged: only the commit that makes a loaded file bigger, and only while over the ceiling ----------

def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def over(root):
    """A repo whose committed state is already over the ceiling."""
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    put(root, "vault/memory/decisions.md", blob(budget.ALWAYS_MAX))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


def test_staged_growing_a_loaded_file_while_over_is_blocked(over):
    put(over, "vault/memory/decisions.md", blob(budget.ALWAYS_MAX + 10))
    git(over, "add", "-A")
    r = run(over, "--staged")
    assert r.returncode == 1 and "OVER" in r.stdout


def test_staged_shrinking_while_still_over_is_allowed(over):
    put(over, "vault/memory/decisions.md", blob(budget.ALWAYS_MAX - 10))
    git(over, "add", "-A")
    assert run(over).returncode == 1                       # the state is still over (the plain report says so) ...
    assert run(over, "--staged").returncode == 0           # ... but the commit that only shrinks is let through


def test_staged_an_unrelated_file_while_over_is_allowed(over):
    put(over, "vault/notes/life/n.md", "# a note\n")
    git(over, "add", "-A")
    assert run(over, "--staged").returncode == 0


def test_staged_growing_while_under_the_ceiling_is_allowed(root):
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    put(root, "vault/CLAUDE.md", blob(5000))
    git(root, "add", "-A")
    assert run(root, "--staged").returncode == 0


def test_staged_growing_a_skill_description_counts_too(over):
    skill(over, "s", "d" * 20)
    git(over, "add", "-A")
    git(over, "commit", "-q", "-m", "skill")
    skill(over, "s", "d" * 400)
    git(over, "add", "-A")
    assert run(over, "--staged").returncode == 1


def test_staged_outside_a_git_repo_is_not_verified(root):
    put(root, "vault/memory/decisions.md", blob(budget.ALWAYS_MAX))
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(root / "vault"), "--root", str(root), "--staged"],
                       capture_output=True, text=True, env={"GIT_CEILING_DIRECTORIES": str(root.parent), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout
