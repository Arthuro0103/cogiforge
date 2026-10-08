"""Paired tests for new_project.py. NEW_PROJECT_PATH points to another copy (used by mutation).

Every test works on a temporary copy of the real vault, never on the vault itself."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOL = os.environ.get("NEW_PROJECT_PATH") or str(Path(__file__).with_name("new_project.py"))
TARGET = "A small app exists and one friend uses it every week"


@pytest.fixture
def vault(tmp_path):
    dst = tmp_path / "vault"
    shutil.copytree(ROOT / "vault", dst)
    return dst


def run(vault, name, *args, target=TARGET):
    cmd = [sys.executable, TOOL, name, "--vault", str(vault), *args]
    if target is not None:
        cmd += ["--target", target]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def tree(vault):
    return sorted((str(p.relative_to(vault)), p.read_bytes() if p.is_file() else None)
                  for p in vault.rglob("*"))


def check(script, vault, *args):
    return subprocess.run([sys.executable, script, "--vault", str(vault), *args],
                          capture_output=True, text=True, cwd=ROOT).returncode


def test_creates_the_project_and_the_vault_still_passes(vault):
    r = run(vault, "my-app", "--type", "software")
    assert r.returncode == 0, r.stdout + r.stderr
    text = (vault / "projects/my-app/instructions.md").read_text()
    assert text.startswith("---\ntype: software\nstatus: active\n")
    assert f"declared_target: {TARGET}\n" in text
    assert "## Quick facts" in text and "## Open" in text
    assert check("core/gate.py", vault) == 0
    assert check("core/ring.py", vault, "--gate") == 0
    assert check("tools/hub.py", vault, "--check") == 0


def test_index_row_goes_right_after_the_last_table_row(vault):
    run(vault, "my-app", "--what", "my small app", "--status", "paused")
    lines = (vault / "projects/_index.md").read_text().split("\n")
    i = next(k for k, l in enumerate(lines) if "projects/my-app/instructions" in l)
    assert lines[i] == r"| [[projects/my-app/instructions\|my-app]] | paused | software | my small app |"
    assert lines[i - 1].startswith("| [[projects/example-my-first-project")
    assert lines[i + 1] == ""


def test_the_target_is_copied_unchanged_even_with_yaml_characters(vault):
    odd = 'It works: "really" # and nothing else'
    assert run(vault, "odd", target=odd).returncode == 0
    from json import dumps
    assert f"declared_target: {dumps(odd)}\n" in (vault / "projects/odd/instructions.md").read_text()


def test_the_file_says_nothing_else_about_the_user(vault):
    run(vault, "my-app")
    text = (vault / "projects/my-app/instructions.md").read_text()
    front = text.split("---")[1]
    assert sorted(l.split(":")[0] for l in front.strip().split("\n")) == ["declared_target", "status", "type"]
    assert text.count(TARGET) == 1  # the user's sentence appears once, in the frontmatter


@pytest.mark.parametrize("name", ["", "Upper", "has space", "a/b", "..", "a..b", "x-", "a--b", "a_b", "x" * 41, "café"])
def test_invalid_names_are_refused_and_nothing_is_written(vault, name):
    before = tree(vault)
    r = run(vault, name)
    assert r.returncode == 1, name
    assert "ERROR" in r.stderr and "Nothing was written" in r.stderr
    assert tree(vault) == before


def test_name_starting_with_a_hyphen_is_never_written(vault):
    before = tree(vault)
    assert run(vault, "-x").returncode in (1, 2)
    assert tree(vault) == before


def test_name_of_exactly_40_characters_is_accepted(vault):
    assert run(vault, "a" * 40).returncode == 0


def test_existing_folder_is_refused_and_left_alone(vault):
    before = tree(vault)
    r = run(vault, "example-my-first-project")
    assert r.returncode == 1 and "already exists" in r.stderr
    assert tree(vault) == before


def test_running_twice_fails_the_second_time_without_touching_anything(vault):
    assert run(vault, "my-app").returncode == 0
    before = tree(vault)
    assert run(vault, "my-app").returncode == 1
    assert tree(vault) == before
    assert (vault / "projects/_index.md").read_text().count("projects/my-app/instructions") == 1


@pytest.mark.parametrize("target", ["", "   ", "describe in one sentence what exists in the world when this project succeeds"])
def test_empty_or_placeholder_target_is_refused(vault, target):
    before = tree(vault)
    r = run(vault, "my-app", target=target)
    assert r.returncode == 1 and "--target" in r.stderr
    assert tree(vault) == before


def test_missing_target_is_a_usage_error(vault):
    assert run(vault, "my-app", target=None).returncode == 2
    assert not (vault / "projects/my-app").exists()


def test_bad_status_and_pipe_in_text_are_refused(vault):
    assert run(vault, "my-app", "--status", "done").returncode == 1
    assert run(vault, "my-app", "--what", "a | b").returncode == 1
    assert run(vault, "my-app", "--type", "a\nb").returncode == 1
    assert not (vault / "projects/my-app").exists()


def test_missing_index_refuses_and_creates_nothing(vault):
    (vault / "projects/_index.md").unlink()
    before = tree(vault)
    r = run(vault, "my-app")
    assert r.returncode == 1 and "_index.md" in r.stderr
    assert tree(vault) == before


def test_index_without_a_table_refuses_and_creates_nothing(vault):
    (vault / "projects/_index.md").write_text("---\ntype: index\n---\n\n# Projects\n\nno table here\n")
    before = tree(vault)
    r = run(vault, "my-app")
    assert r.returncode == 1 and "no projects table" in r.stderr
    assert tree(vault) == before


def test_dry_run_prints_the_plan_and_writes_nothing(vault):
    before = tree(vault)
    r = run(vault, "my-app", "--dry-run")
    assert r.returncode == 0
    assert "projects/my-app/instructions.md" in r.stdout and "[[projects/my-app/instructions" in r.stdout
    assert TARGET in r.stdout
    assert tree(vault) == before


def test_dry_run_also_refuses_invalid_input(vault):
    assert run(vault, "Bad Name", "--dry-run").returncode == 1


def test_a_failing_check_gives_rc1_and_names_the_reason(vault):
    (vault / "areas.txt").unlink(missing_ok=True)
    (vault / "projects/stray").mkdir()  # a project outside the index: hub --check must fail
    (vault / "projects/stray/instructions.md").write_text("# stray\n")
    r = run(vault, "my-app")
    assert r.returncode == 1
    assert "stray" in r.stdout + r.stderr and "CHECK FAILED" in r.stderr
    assert (vault / "projects/my-app/instructions.md").exists()  # nothing is undone
