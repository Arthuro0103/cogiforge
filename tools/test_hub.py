"""Paired tests for hub.py. HUB_PATH points to another copy (used by mutation)."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
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


# ---- the cap: a root never grows with the project ----------------------------

def many(vault, n, name="p"):
    return project(vault, name, extras=[f"f{i:03d}.md" for i in range(n)])


def test_a_project_at_the_cap_still_lists_everything_in_the_root(tmp_path):
    d = many(tmp_path, 40)
    assert hub(tmp_path).returncode == 0
    text = (d / "instructions.md").read_text()
    assert text.count("[[projects/p/f") == 40 and not (d / "_files.md").exists()


def test_one_file_over_the_cap_moves_the_list_to_files_md(tmp_path):
    d = many(tmp_path, 41)
    assert hub(tmp_path).returncode == 0
    root, listing = (d / "instructions.md").read_text(), (d / "_files.md").read_text()
    assert root.count("[[projects/p/f") == 0 and "[[projects/p/_files|all 41 files of this project]]" in root
    assert listing.count("[[projects/p/f") == 41 and "[[projects/p/f040|f040]]" in listing
    assert "text that survives" in root


def test_the_root_stays_small_however_many_files_the_project_has(tmp_path):
    d = many(tmp_path, 500)
    hub(tmp_path)
    assert len((d / "instructions.md").read_bytes()) < 600


def test_the_overflow_list_does_not_list_itself_and_a_second_run_changes_nothing(tmp_path):
    d = many(tmp_path, 45)
    hub(tmp_path)
    first = ((d / "instructions.md").read_text(), (d / "_files.md").read_text())
    assert hub(tmp_path).returncode == 0
    assert ((d / "instructions.md").read_text(), (d / "_files.md").read_text()) == first
    assert "[[projects/p/_files|_files]]" not in first[1] and "all 45 files" in first[0]


def test_check_fails_when_the_overflow_list_is_missing_or_stale(tmp_path):
    d = many(tmp_path, 41)
    hub(tmp_path)
    assert hub(tmp_path, "--check").returncode == 0
    (d / "_files.md").unlink()
    assert hub(tmp_path, "--check").returncode == 1
    hub(tmp_path)
    (d / "zzz.md").write_text("z")
    assert hub(tmp_path, "--check").returncode == 1
    hub(tmp_path)
    assert "all 42 files" in (d / "instructions.md").read_text() and hub(tmp_path, "--check").returncode == 0


def test_check_reports_a_missing_overflow_list_as_stale_even_when_the_root_has_no_block(tmp_path):
    many(tmp_path, 41)
    r = hub(tmp_path, "--check")
    assert r.returncode == 1
    assert r.stdout.split() == ["STALE", "p"]


def test_check_does_not_write_the_overflow_list(tmp_path):
    d = many(tmp_path, 41)
    assert hub(tmp_path, "--check").returncode == 1
    assert not (d / "_files.md").exists()


def test_dry_run_does_not_write_the_overflow_list(tmp_path):
    d = many(tmp_path, 41)
    hub(tmp_path, "--dry-run")
    assert not (d / "_files.md").exists()


def test_shrinking_back_under_the_cap_inlines_the_list_and_removes_the_generated_file(tmp_path):
    d = many(tmp_path, 41)
    hub(tmp_path)
    (d / "f000.md").unlink()
    hub(tmp_path)
    assert not (d / "_files.md").exists()
    assert (d / "instructions.md").read_text().count("[[projects/p/f") == 40


def test_a_files_md_the_user_wrote_is_never_deleted(tmp_path):
    d = many(tmp_path, 3)
    (d / "_files.md").write_text("my own page, not generated\n")
    hub(tmp_path)
    assert (d / "_files.md").read_text() == "my own page, not generated\n"


def test_every_file_keeps_an_edge_so_none_becomes_an_orphan(tmp_path):
    import ring
    d = many(tmp_path, 60)
    hub(tmp_path)
    notes, degree = ring.analyze(tmp_path)
    assert ring.chk_orphans(notes, degree) == []
    assert degree["projects/p/_files.md"] == 61          # 60 files + the root
