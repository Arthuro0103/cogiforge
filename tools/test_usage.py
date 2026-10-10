"""Paired tests for usage.py: what counts as a used note, what is stale, and what is not measured."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

USAGE = str(Path(__file__).with_name("usage.py"))
TODAY = "2026-10-08"


def write(vault, files):
    for rel, text in files.items():
        p = Path(vault) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Path(vault)


def note(area="life", date="2026-01-01", project="p", extra="", body="text"):
    return f"---\ntype: note\narea: {area}\nproject: {project}\ndate: {date}\n{extra}---\n# Title of {area} {date}\n\n{body}\n"


def usage(vault, *args):
    return subprocess.run([sys.executable, USAGE, "--vault", str(vault), "--today", TODAY, *args], capture_output=True, text=True)


def states(vault):
    """{note path: state} through the JSON of the report's `idle` mode is not enough: read the table instead."""
    out = json.loads(usage(vault, "--json").stdout)
    return out["summary"]


def one(vault, area="life"):
    return states(vault)[area]


def test_a_note_linked_from_a_project_file_is_used(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(), "projects/p/brief.md": "see [[notes/life/n]]\n"})
    assert one(v)["used"] == 1


@pytest.mark.parametrize("kind", ["article", "brief", "routine"])
def test_a_note_linked_from_an_output_type_is_used(tmp_path, kind):
    out = f"---\ntype: {kind}\n---\n# Out\n\nuses [[notes/life/n]]\n"
    v = write(tmp_path, {"notes/life/n.md": note(), "notes/technology/out.md": out})
    assert one(v)["used"] == 1


def test_a_note_linked_only_from_another_plain_note_is_not_used(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(), "notes/technology/m.md": note(area="technology", body="[[notes/life/n]]")})
    assert one(v)["used"] == 0


def test_an_output_note_linking_to_itself_is_not_a_use_of_itself(tmp_path):
    own = "---\ntype: article\narea: life\ndate: 2026-01-01\n---\n# Out\n\nsee [[notes/life/out]]\n"
    v = write(tmp_path, {"notes/life/out.md": own})
    assert one(v)["used"] == 0


def test_a_note_linking_out_is_not_used_by_that(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(body="[[projects/p/brief]]"), "projects/p/brief.md": "x\n"})
    assert one(v)["used"] == 0


def test_a_link_inside_code_is_not_a_use(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(), "projects/p/brief.md": "`[[notes/life/n]]`\n```\n[[notes/life/n]]\n```\n"})
    assert one(v)["used"] == 0


def test_a_link_by_bare_name_is_a_use(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(), "projects/p/brief.md": "see [[n]]\n"})
    assert one(v)["used"] == 1


def test_a_note_cited_in_the_ask_log_is_used(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(), "memory/ask-log.jsonl": json.dumps(
        {"date": "2026-09-01", "question": "q", "cited": ["notes/life/n"]}) + "\n"})
    r = usage(v)
    assert one(v)["used"] == 1 and "1 distinct note(s) cited" in r.stdout


def test_a_malformed_log_line_is_ignored_and_reported(tmp_path):
    good = json.dumps({"date": "2026-09-01", "question": "q", "cited": ["notes/life/n"]})
    v = write(tmp_path, {"notes/life/n.md": note(), "memory/ask-log.jsonl": f"not json\n{good}\n{{\"date\": 1}}\n"})
    r = usage(v)
    assert one(v)["used"] == 1 and "2 malformed line(s)" in r.stdout


def test_age_decides_idle_or_stale_at_exactly_the_limit(tmp_path):
    v = write(tmp_path, {"notes/life/a.md": note(date="2026-07-10"),   # 90 days before 2026-10-08
                         "notes/life/b.md": note(date="2026-07-11")})  # 89 days
    s = one(v)
    assert s["stale"] == 1 and s["idle"] == 1


def test_days_option_moves_the_limit(tmp_path):
    v = write(tmp_path, {"notes/life/a.md": note(date="2026-10-01")})
    assert json.loads(usage(v, "--json").stdout)["summary"]["life"]["idle"] == 1
    assert json.loads(usage(v, "--json", "--days", "5").stdout)["summary"]["life"]["stale"] == 1


@pytest.mark.parametrize("fm", ["", "date: soon\n", "date:\n"])
def test_a_note_with_no_readable_date_is_undated_never_guessed(tmp_path, fm):
    v = write(tmp_path, {"notes/life/n.md": f"---\ntype: note\n{fm}---\n# T\n\nbody\n"})
    s = one(v)
    assert s["undated"] == 1 and s["stale"] == 0 and s["idle"] == 0


def test_a_used_note_is_never_stale_however_old(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(date="2020-01-01"), "projects/p/brief.md": "[[notes/life/n]]\n"})
    s = one(v)
    assert s["used"] == 1 and s["stale"] == 0


def test_the_table_has_one_row_per_area_and_a_total(tmp_path):
    v = write(tmp_path, {"notes/life/a.md": note(date="2026-10-01"), "notes/technology/b.md": note(area="technology"),
                         "notes/technology/c.md": note(area="technology", date="2020-01-01")})
    r = usage(v)
    assert "| life | 1 |" in r.stdout and "| technology | 2 |" in r.stdout and "| **all** | 3 |" in r.stdout
    assert "| **all** | 3 | 0 (0%) | 1 | 2 (67%) | 0 |" in r.stdout


def test_no_notes_is_not_verified_never_a_zero_percent(tmp_path):
    v = write(tmp_path, {"projects/p/instructions.md": "x\n", "inbox/c.md": "x\n"})
    r = usage(v)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout and "(0%)" not in r.stdout and "| **all**" not in r.stdout


def test_a_missing_vault_is_not_verified(tmp_path):
    r = usage(tmp_path / "none")
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_with_no_project_file_and_no_log_it_says_the_zero_is_real(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note()})
    assert "nothing could have used a note" in usage(v).stdout


def test_inbox_and_projects_are_not_counted_as_notes(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note(), "inbox/i.md": "x\n", "projects/p/b.md": "x\n"})
    assert sum(a["notes"] for a in states(v).values()) == 1


def test_bad_arguments_are_rc_2(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note()})
    assert usage(v, "--today", "yesterday").returncode == 2
    assert usage(v, "--days", "0").returncode == 2
    assert usage(v, "idle").returncode == 2           # idle needs --project


# ---- idle --project -----------------------------------------------------------

def test_idle_lists_the_oldest_unused_notes_of_the_project_only(tmp_path):
    v = write(tmp_path, {
        "notes/life/new.md": note(date="2026-10-01"),
        "notes/life/old.md": note(date="2025-01-01"),
        "notes/life/mid.md": note(date="2026-03-01"),
        "notes/life/used.md": note(date="2020-01-01"),
        "notes/life/other.md": note(date="2019-01-01", project="q"),
        "projects/p/brief.md": "[[notes/life/used]]\n"})
    r = usage(v, "idle", "--project", "p", "--top", "2")
    lines = r.stdout.strip().splitlines()
    assert r.returncode == 0 and len(lines) == 2
    assert lines[0].startswith("[[notes/life/old|") and lines[1].startswith("[[notes/life/mid|")
    assert "stale" in lines[0] and "used" not in r.stdout and "other" not in r.stdout


def test_idle_default_is_three(tmp_path):
    v = write(tmp_path, {f"notes/life/n{i}.md": note(date=f"2025-0{i + 1}-01") for i in range(5)})
    assert len(usage(v, "idle", "--project", "p").stdout.strip().splitlines()) == 3


def test_idle_with_nothing_to_show_says_so(tmp_path):
    v = write(tmp_path, {"notes/life/n.md": note()})
    r = usage(v, "idle", "--project", "nobody")
    assert r.returncode == 0 and "No idle note" in r.stdout


def test_idle_puts_an_undated_note_after_the_dated_ones(tmp_path):
    v = write(tmp_path, {"notes/life/dated.md": note(date="2026-09-01"),
                         "notes/life/nodate.md": "---\ntype: note\nproject: p\n---\n# T\n\nbody\n"})
    lines = usage(v, "idle", "--project", "p").stdout.strip().splitlines()
    assert lines[0].startswith("[[notes/life/dated|") and "undated" in lines[1]


def test_idle_with_no_notes_is_not_verified(tmp_path):
    v = write(tmp_path, {"projects/p/instructions.md": "x\n"})
    assert usage(v, "idle", "--project", "p").returncode == 3
