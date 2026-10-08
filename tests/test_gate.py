"""gate.py: each check has a pair (fails / passes) and the parser limits are pinned."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import gate
from helpers import note, vault

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "gate.py"


def checks_of(tmp_path, files, **kw):
    v = vault(tmp_path, files)
    _, failures = gate.audit(v, **kw)
    return sorted((f.file, f.check) for f in failures)


# ---- frontmatter -------------------------------------------------------------

@pytest.mark.parametrize("fm", [
    "book: Peak: Secrets from the Science",   # colon without quotes
    "title: 'unclosed",                       # open quote
    "tags: [a, b",                            # open inline list
    "author:\n  name: x",                     # nested map: outside the subset
    "key without a colon",
    "desc: |", "desc: >", "ref: &anchor", "ref: *anchor", "type: !tag", "x: {a: b}",
    "a: value\n  - item",   # list item over a value that is not a list
    "\tarea: x",                              # tab
    "tags:\n \t- a",                          # tab in the middle of an item's indentation
])
def test_invalid_frontmatter_fails(tmp_path, fm):
    r = checks_of(tmp_path, {"x.md": f"---\n{fm}\n---\nbody\n"})
    assert r == [("x.md", "frontmatter")]


@pytest.mark.parametrize("fm", [
    "title: Plain text", "title: \"with: colon inside quotes\"", "title: 'single quotes'",
    "tags: [a, b, \"c d\"]", "tags:\n  - a\n  - b", "# comment\nempty:\nurl: https://x.org/a",
    "done: yes  # comment at the end", "list: []",
])
def test_valid_frontmatter_passes(tmp_path, fm):
    assert checks_of(tmp_path, {"x.md": f"---\n{fm}\n---\nbody\n"}) == []


def test_no_frontmatter_passes_and_open_frontmatter_fails(tmp_path):
    r = checks_of(tmp_path, {"a.md": "body only\n", "b.md": "---\narea: x\nnever closes\n"})
    assert r == [("b.md", "frontmatter")]


def test_parser_returns_types():
    d, error = gate.parse_fm(["a: x", "b: [1, 'y']", "c:", "  - i", "  - j", "d:"])
    assert error is None and d == {"a": "x", "b": ["1", "y"], "c": ["i", "j"], "d": None}


# ---- area --------------------------------------------------------------------

def test_area_ok_passes(tmp_path):
    assert checks_of(tmp_path, {"notes/life/a.md": note("life")}) == []


@pytest.mark.parametrize("files, reason", [
    ({"notes/life/a.md": note("technology")}, "lives in notes/technology"),   # folder != area
    ({"notes/life/a.md": "---\ntitle: x\n---\n"}, "missing area"),
    ({"notes/life/a.md": note("invented")}, "not in the configured list"),
    ({"notes/a.md": note("life")}, "loose in the root"),
    ({"notes/other/a.md": note("life")}, "no configured area"),
])
def test_wrong_area_fails(tmp_path, files, reason):
    v = vault(tmp_path, files)
    _, failures = gate.audit(v)
    assert [f.check for f in failures] == ["area"] and reason in failures[0].msg


def test_area_outside_notes_does_not_apply(tmp_path):
    assert checks_of(tmp_path, {"inbox/a.md": "x\n", "projects/a.md": note("whatever")}) == []


def test_area_does_not_count_twice_when_frontmatter_already_failed(tmp_path):
    r = checks_of(tmp_path, {"notes/life/a.md": "---\nbook: A: B\n---\n"})
    assert r == [("notes/life/a.md", "frontmatter")]


def test_areas_configurable_by_file(tmp_path):
    files = {"areas.txt": "# mine\nstudy\nwork: job\n", "notes/study/a.md": note("study"),
             "notes/work/b.md": note("job"), "notes/life/c.md": note("life")}
    assert checks_of(tmp_path, files) == [("notes/life/c.md", "area")]


# ---- dead-link ---------------------------------------------------------------

@pytest.mark.parametrize("link", [
    "[[b]]", "[[b|alias]]", "[[b#section]]", "[[B]]", "![[b]]", "[[notes/life/b]]", "[[notes/life/b.md]]",
    "[[../life/b]]", "[[life/b]]",
])
def test_live_link_passes(tmp_path, link):
    files = {"notes/life/a.md": note("life", f"{link}\n"), "notes/life/b.md": note("life")}
    assert checks_of(tmp_path, files) == []


@pytest.mark.parametrize("link", ["[[does-not-exist]]", "[[b-almost]]", "[[other/folder/b]]", "[[b.png]]"])
def test_dead_link_fails(tmp_path, link):
    files = {"notes/life/a.md": note("life", f"{link}\n"), "notes/life/b.md": note("life")}
    assert checks_of(tmp_path, files) == [("notes/life/a.md", "dead-link")]


def test_link_in_code_is_not_a_link(tmp_path):
    body = "```\n[[dead-in-fence]]\n```\n`[[dead-inline]]`\n~~~~\n```\n[[still-fenced]]\n~~~~\n"
    assert checks_of(tmp_path, {"a.md": body}) == []


def test_anchor_to_the_file_itself_does_not_count(tmp_path):
    assert checks_of(tmp_path, {"a.md": "[[#section]] and [[^block]]\n"}) == []


def test_counts_each_occurrence(tmp_path):
    v = vault(tmp_path, {"a.md": "[[x1]] [[x2]]\n[[x3]]\n"})
    _, failures = gate.audit(v)
    assert len(failures) == 3


# ---- broken-link -------------------------------------------------------------

def test_broken_link_fails(tmp_path):
    r = checks_of(tmp_path, {"a.md": "see [[note with a name\nthat is long]] here\n"})
    assert r == [("a.md", "broken-link")]


def test_broken_link_does_not_become_dead_link_and_counts_per_line(tmp_path):
    v = vault(tmp_path, {"a.md": "[[one\nlink]]\n[[two\nlink]]\n"})
    _, failures = gate.audit(v)
    assert [f.check for f in failures] == ["broken-link", "broken-link"]


def test_whole_link_and_code_pass(tmp_path):
    body = "[[b]] and [[b]] on the same line\n```\n[[broken\n```\n`[[loose`\n"
    assert checks_of(tmp_path, {"a.md": body, "b.md": "x\n"}) == []


# ---- dead-target -------------------------------------------------------------

def test_existing_target_passes(tmp_path):
    files = {"a.md": "---\ntarget: x/b.md\n---\n", "x/b.md": "b\n", "c.md": "---\ntarget: x/b\n---\n"}
    assert checks_of(tmp_path, files) == []


def test_missing_target_fails(tmp_path):
    assert checks_of(tmp_path, {"a.md": "---\ntarget: x/some.md\n---\n"}) == [("a.md", "dead-target")]


def test_target_that_only_matches_by_basename_with_a_declared_path_fails(tmp_path):
    files = {"a.md": "---\ntarget: wrong-folder/b.md\n---\n", "x/b.md": "b\n"}
    assert checks_of(tmp_path, files) == [("a.md", "dead-target")]


def test_target_without_a_slash_resolves_by_name(tmp_path):
    assert checks_of(tmp_path, {"a.md": "---\ntarget: b\n---\n", "x/b.md": "b\n"}) == []


def test_target_list_none_directory_and_absolute(tmp_path):
    d = tmp_path / "outside"
    d.mkdir()
    files = {"a.md": f"---\ntarget: [none, x, '{d}']\n---\n", "x/b.md": "b\n"}
    assert checks_of(tmp_path / "v", files) == []


def test_target_in_a_list_counts_only_the_dead_one(tmp_path):
    files = {"a.md": "---\ntarget: [x/b.md, x/dead.md]\n---\n", "x/b.md": "b\n"}
    v = vault(tmp_path, files)
    _, failures = gate.audit(v)
    assert [(f.file, f.check) for f in failures] == [("a.md", "dead-target")]


# ---- CLI ---------------------------------------------------------------------

def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_cli_rc_json_and_filter(tmp_path):
    v = vault(tmp_path, {"a.md": "[[dead]]\n", "b.md": "[[broken\nx]]\n", "c.md": "ok\n"})
    r = run("--vault", str(v), "--json")
    d = json.loads(r.stdout)
    assert r.returncode == 1 and d["files"] == 3 and d["failed"] == 2
    assert d["checks"]["dead-link"]["notes"] == 1 and d["checks"]["broken-link"]["occurrences"] == 1
    only = json.loads(run("--vault", str(v), "--json", "--check", "dead-link").stdout)
    assert [f["check"] for f in only["failures"]] == ["dead-link"]


def test_cli_clean_exits_zero(tmp_path):
    v = vault(tmp_path, {"a.md": "[[b]]\n", "b.md": "[[a]]\n"})
    assert run("--vault", str(v)).returncode == 0


def test_cli_missing_vault_exits_2(tmp_path):
    assert run("--vault", str(tmp_path / "does-not-exist")).returncode == 2


def test_file_outside_the_vault_exits_2_never_clean_and_no_traceback(tmp_path):
    """A draft OUTSIDE the vault cannot be reported as checked: the gate resolves links and areas
    relative to the vault, so checking what is outside it would be an OK that touched nothing.
    Found on 03/10 while writing the README: the gate crashed with a traceback (rc 1, ValueError)."""
    v = vault(tmp_path / "v", {"notes/life/a.md": note("life", "[[b]]\n"), "notes/life/b.md": note("life", "[[a]]\n")})
    draft = tmp_path / "draft.md"  # sibling of the vault, not inside it
    draft.write_text("---\narea: nothing-to-do-with-it\n---\n# Draft\n\nText.\n")
    r = run("--vault", str(v), str(draft))
    assert r.returncode == 2
    assert "outside" in r.stderr and "Traceback" not in r.stderr and "Traceback" not in r.stdout


TASK_WITH_TIME = ("---\ntags:\n  - task\ntitle: Buy batteries\nstatus: open\ntimeEntries:\n"
                  "  - startTime: 2026-10-03T10:00:00-03:00\n    endTime: 2026-10-03T10:20:00-03:00\n---\n")  # what TaskNotes writes when time is logged


def test_plugin_task_frontmatter_is_not_judged_by_the_subset(tmp_path):
    """tasks/ belongs to the TaskNotes plugin, whose YAML (list of maps in timeEntries) is valid but
    falls outside the gate's subset. Found on 03/10 measuring a task with logged time."""
    assert checks_of(tmp_path, {"tasks/t.md": TASK_WITH_TIME}) == []


def test_the_same_yaml_outside_tasks_still_fails(tmp_path):
    assert checks_of(tmp_path, {"notes/life/t.md": TASK_WITH_TIME}) == [("notes/life/t.md", "frontmatter")]


def test_dead_link_inside_the_task_still_fails(tmp_path):
    task = "---\ntags:\n  - task\nprojects:\n  - \"[[projects/does-not-exist/instructions]]\"\n---\n"
    assert checks_of(tmp_path, {"tasks/t.md": task}) == [("tasks/t.md", "dead-link")]


@pytest.mark.skipif(sys.platform == "win32", reason="chmod(0) cannot make a file unreadable on Windows (POSIX permission bits)")
def test_cli_unreadable_file_exits_3_never_clean(tmp_path):
    v = vault(tmp_path, {"a.md": "clean\n"})
    (v / "a.md").chmod(0)
    try:
        r = run("--vault", str(v))
    finally:
        (v / "a.md").chmod(0o644)
    assert r.returncode == 3 and "UNREADABLE" in r.stdout


def test_cli_unknown_check_exits_2(tmp_path):
    assert run("--vault", str(vault(tmp_path, {"a.md": "x\n"})), "--check", "invented").returncode == 2


# ---- limits that mutation demanded ---------------------------------------------

def test_comment_at_the_end_of_a_value_with_a_colon_passes(tmp_path):
    assert checks_of(tmp_path, {"x.md": "---\ntitle: value  # note: ok\n---\n"}) == []


def test_target_with_a_declared_path_only_counts_from_the_root(tmp_path):
    files = {"a.md": "---\ntarget: life/b.md\n---\n", "notes/life/b.md": note("life")}
    assert checks_of(tmp_path, files) == [("a.md", "dead-target")]


def test_frontmatter_with_crlf_passes(tmp_path):
    v = vault(tmp_path, {})
    (v / "x.md").write_bytes(b"---\r\narea: life\r\n---\r\nbody [[x]]\r\n")
    assert gate.audit(v)[1] == []


def test_tool_folders_are_not_scanned_or_indexed(tmp_path):
    files = {".obsidian/x.md": "[[dead]]\n", ".git/y.md": "[[dead]]\n", "a.md": "[[x]]\n"}
    assert checks_of(tmp_path, files) == [("a.md", "dead-link")]  # `x` only exists in .obsidian: it does not count


def test_bare_name_finds_the_note_in_the_same_folder_and_otherwise_any(tmp_path):
    v = vault(tmp_path, {"x/a.md": "x\n", "x/b.md": "x\n", "y/b.md": "y\n", "z/c.md": "z\n"})
    idx = gate.Index(v)
    assert idx.find("b", "x/a.md") == "x/b.md" and idx.find("b", "y/c.md") == "y/b.md"
    assert idx.find("b", "z/c.md") in ("x/b.md", "y/b.md")


def test_unreadable_is_a_non_utf8_file_never_clean(tmp_path):
    v = vault(tmp_path, {})
    (v / "x.md").write_bytes(b"\xff\xfe\xfa junk")
    assert [f.check for f in gate.audit(v)[1]] == ["UNREADABLE"]
    assert run("--vault", str(v)).returncode == 3
