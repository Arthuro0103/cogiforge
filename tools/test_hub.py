"""Paired tests for hub.py. HUB_PATH points to another copy (used by mutation)."""
import os
import subprocess
import sys
from pathlib import Path

HUB = os.environ.get("HUB_PATH") or str(Path(__file__).with_name("hub.py"))


def hub(vault, *args):
    return subprocess.run([sys.executable, HUB, "--vault", str(vault), *args],
                          capture_output=True, text=True)


def project(vault, name="p", extras=()):
    d = vault / "projects" / name
    d.mkdir(parents=True)
    (d / "instructions.md").write_text("# p\n\ntext that survives\n")
    for e in extras:
        (d / e).parent.mkdir(parents=True, exist_ok=True)
        (d / e).write_text("x")
    return d


def test_file_outside_the_block_fails_and_then_passes(tmp_path):
    d = project(tmp_path, extras=["a.md", "sub/b.md"])
    assert hub(tmp_path, "--check").returncode == 1
    assert hub(tmp_path).returncode == 0
    assert hub(tmp_path, "--check").returncode == 0
    text = (d / "instructions.md").read_text()
    assert "text that survives" in text
    assert "[[projects/p/a|a]]" in text and "[[projects/p/sub/b|b]]" in text
    assert "[[projects/p/instructions" not in text


def test_project_without_extras_passes_untouched(tmp_path):
    d = project(tmp_path)
    before = (d / "instructions.md").read_text()
    assert hub(tmp_path, "--check").returncode == 0
    assert hub(tmp_path).returncode == 0
    assert (d / "instructions.md").read_text() == before


def test_writing_twice_leaves_one_block(tmp_path):
    d = project(tmp_path, extras=["a.md"])
    hub(tmp_path)
    hub(tmp_path)
    assert (d / "instructions.md").read_text().count("<!-- hub:start -->") == 1


def test_new_file_after_the_block_fails_again(tmp_path):
    d = project(tmp_path, extras=["a.md"])
    hub(tmp_path)
    (d / "c.md").write_text("c")
    assert hub(tmp_path, "--check").returncode == 1


def test_dry_run_does_not_write(tmp_path):
    d = project(tmp_path, extras=["a.md"])
    before = (d / "instructions.md").read_text()
    r = hub(tmp_path, "--dry-run")
    assert "[[projects/p/a|a]]" in r.stdout
    assert (d / "instructions.md").read_text() == before


def test_unknown_flag_refuses_without_writing(tmp_path):
    d = project(tmp_path, extras=["a.md"])
    before = (d / "instructions.md").read_text()
    assert hub(tmp_path, "--bogus").returncode == 2
    assert (d / "instructions.md").read_text() == before


def test_project_missing_from_the_index_fails(tmp_path):
    project(tmp_path)
    (tmp_path / "projects" / "_index.md").write_text("| other | active |\n")
    assert hub(tmp_path, "--check").returncode == 1
    (tmp_path / "projects" / "_index.md").write_text("| p | active |\n")
    assert hub(tmp_path, "--check").returncode == 0


def test_selftest():
    assert subprocess.run([sys.executable, HUB, "--selftest"]).returncode == 0


def test_check_does_not_write(tmp_path):
    d = project(tmp_path, extras=["a.md"])
    before = (d / "instructions.md").read_text()
    assert hub(tmp_path, "--check").returncode == 1
    assert (d / "instructions.md").read_text() == before


def test_rewriting_an_old_block_replaces_it_instead_of_duplicating(tmp_path):
    d = project(tmp_path, extras=["a.md"])
    hub(tmp_path)
    (d / "c.md").write_text("c")
    hub(tmp_path)
    text = (d / "instructions.md").read_text()
    assert text.count("<!-- hub:start -->") == 1 and "[[projects/p/c|c]]" in text
