"""Paired tests for cool.py: the older dated lines move word for word, the newest stay, nothing is rewritten."""
import subprocess
import sys
from pathlib import Path

COOL = str(Path(__file__).with_name("cool.py"))
RING = str(Path(__file__).resolve().parent.parent / "core" / "ring.py")

MEMORY = """# Decisions

Some intro that is not an entry.

- 2026-01-01: "oldest, said in January"
- 2026-03-10: "third"
  a continuation line that belongs to the entry above
- 2026-02-02: "second oldest"
- 2026-05-05: "newest"
- 2026-04-04: "fourth"

A closing line that is not an entry.
"""


def vault(tmp_path, text=MEMORY, name="decisions"):
    f = tmp_path / "memory" / f"{name}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    (tmp_path / "home.md").write_text("[[memory/decisions]]\n", encoding="utf-8")
    return tmp_path


def cool(v, *args, file="memory/decisions.md"):
    return subprocess.run([sys.executable, COOL, file, "--vault", str(v), "--today", "2026-10-08", *args], capture_output=True, text=True)


def read(v, rel="memory/decisions.md"):
    return (Path(v) / rel).read_text(encoding="utf-8")


def test_the_plan_writes_nothing(tmp_path):
    v = vault(tmp_path)
    r = cool(v, "--keep", "2")
    assert r.returncode == 0 and "Would move 3 of 5" in r.stdout and "Plan only" in r.stdout
    assert read(v) == MEMORY and not (v / "memory/archive").exists()


def test_apply_keeps_the_newest_and_moves_the_older_word_for_word(tmp_path):
    v = vault(tmp_path)
    assert cool(v, "--keep", "2", "--apply").returncode == 0
    mem, arch = read(v), read(v, "memory/archive/decisions.md")
    assert '"newest"' in mem and '"fourth"' in mem
    assert all(s not in mem for s in ('"oldest, said in January"', '"second oldest"', '"third"'))
    for line in ('- 2026-01-01: "oldest, said in January"', '- 2026-02-02: "second oldest"', '- 2026-03-10: "third"',
                 "  a continuation line that belongs to the entry above"):
        assert line in arch.split("\n")                       # moved exactly, indentation included
    assert arch.index("2026-01-01") < arch.index("2026-02-02") < arch.index("2026-03-10")


def test_a_continuation_line_moves_with_its_entry_and_does_not_stay_behind(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "1", "--apply")
    assert "continuation" not in read(v) and "continuation" in read(v, "memory/archive/decisions.md")


def test_lines_that_are_not_entries_stay(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "1", "--apply")
    mem = read(v)
    assert "Some intro that is not an entry." in mem and "A closing line that is not an entry." in mem and mem.startswith("# Decisions")


def test_one_pointer_stays_behind_with_a_full_path_link(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "2", "--apply")
    mem = read(v)
    assert mem.count("[[memory/archive/decisions|") == 1 and "3 older entries" in mem
    assert mem.index("[[memory/archive/decisions|") < mem.index('"newest"')


def test_the_archive_links_back_and_nothing_becomes_an_orphan(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "2", "--apply")
    assert "[[memory/decisions]]" in read(v, "memory/archive/decisions.md")
    r = subprocess.run([sys.executable, RING, "--vault", str(v), "--gate"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_the_whole_text_is_conserved(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "2", "--apply")
    now = [l for l in (read(v) + "\n" + read(v, "memory/archive/decisions.md")).split("\n") if l.strip()]
    for line in [l for l in MEMORY.split("\n") if l.strip()]:
        assert line in now, line


def test_a_second_run_with_nothing_more_to_move_changes_nothing(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "2", "--apply")
    before = (read(v), read(v, "memory/archive/decisions.md"))
    r = cool(v, "--keep", "2", "--apply")
    assert "Nothing to move" in r.stdout and (read(v), read(v, "memory/archive/decisions.md")) == before


def test_a_later_run_appends_and_rewrites_the_pointer_instead_of_duplicating(tmp_path):
    v = vault(tmp_path)
    cool(v, "--keep", "3", "--apply")
    cool(v, "--keep", "1", "--apply")
    mem, arch = read(v), read(v, "memory/archive/decisions.md")
    assert mem.count("[[memory/archive/") == 1 and "4 older entries" in mem
    assert arch.count("\n- 2026-") == 4 and arch.count("# Older entries") == 1


def test_a_tie_on_the_date_keeps_the_later_line(tmp_path):
    v = vault(tmp_path, "- 2026-01-01: \"first\"\n- 2026-01-01: \"second\"\n")
    cool(v, "--keep", "1", "--apply")
    assert '"second"' in read(v) and '"first"' not in read(v)


def test_a_file_with_no_dated_entry_is_not_verified(tmp_path):
    v = vault(tmp_path, "# Decisions\n\nnothing dated here\n")
    r = cool(v, "--keep", "1", "--apply")
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout and read(v) == "# Decisions\n\nnothing dated here\n"


def test_a_missing_file_is_not_verified(tmp_path):
    (tmp_path / "memory").mkdir()
    assert cool(tmp_path, "--keep", "1").returncode == 3


def test_fewer_entries_than_keep_moves_nothing(tmp_path):
    v = vault(tmp_path)
    r = cool(v, "--keep", "9", "--apply")
    assert r.returncode == 0 and "Nothing to move" in r.stdout and read(v) == MEMORY and not (v / "memory/archive").exists()


def test_only_a_memory_file_can_be_cooled(tmp_path):
    v = vault(tmp_path)
    (v / "notes").mkdir()
    (v / "notes/n.md").write_text("- 2026-01-01: x\n", encoding="utf-8")
    for bad in ("notes/n.md", "../memory/decisions.md", "memory/archive/decisions.md", "memory/decisions.txt", "/etc/hosts"):
        assert cool(v, "--keep", "1", "--apply", file=bad).returncode == 2, bad


def test_keep_below_one_is_rejected(tmp_path):
    assert cool(vault(tmp_path), "--keep", "0").returncode == 2


def test_a_different_memory_file_gets_its_own_archive(tmp_path):
    v = vault(tmp_path, name="profile")
    assert cool(v, "--keep", "1", "--apply", file="memory/profile.md").returncode == 0
    assert (v / "memory/archive/profile.md").is_file()
