"""ring.py: a note with no inbound or outbound wikilink is an orphan; inbox is exempt; the gate teaches."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import ring
from helpers import vault

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "ring.py"
PAIR = {"a.md": "goes to [[b]]\n", "b.md": "goes back to [[a]]\n"}


def orphans(tmp_path, files):
    v = vault(tmp_path, {**PAIR, **files})
    notes, deg = ring.analyze(v)
    return ring.chk_orphans(notes, deg)


def test_linked_note_is_not_an_orphan(tmp_path):
    assert orphans(tmp_path, {}) == []


def test_note_with_no_link_is_an_orphan(tmp_path):
    assert orphans(tmp_path, {"loose.md": "nothing here\n"}) == ["loose.md"]


def test_only_an_outbound_or_only_an_inbound_link_is_enough(tmp_path):
    assert orphans(tmp_path, {"out.md": "goes [[a]]\n", "a2.md": "x\n", "a.md": "goes [[b]] and [[a2]]\n"}) == []


def test_dead_link_is_not_an_edge(tmp_path):
    assert orphans(tmp_path, {"only-dead.md": "[[does-not-exist]]\n"}) == ["only-dead.md"]


def test_self_link_is_not_an_edge(tmp_path):
    assert orphans(tmp_path, {"me.md": "[[me]]\n"}) == ["me.md"]


def test_link_in_code_is_not_an_edge(tmp_path):
    assert orphans(tmp_path, {"c.md": "```\n[[a]]\n```\n`[[b]]`\n"}) == ["c.md"]


def test_plain_markdown_link_is_an_edge(tmp_path):
    assert orphans(tmp_path, {"m.md": "see [a](a.md)\n"}) == []


def test_markdown_link_with_an_encoded_space_resolves(tmp_path):
    v = vault(tmp_path, {"m.md": "see [x](sub%20dir/x.md)\n", "sub dir/x.md": "x\n"})
    notes, deg = ring.analyze(v)
    assert ring.chk_orphans(notes, deg) == []


def test_link_to_an_image_is_not_an_edge(tmp_path):
    assert orphans(tmp_path, {"img.png": "x", "i.md": "![[img.png]]\n"}) == ["i.md"]


def test_inbox_is_exempt_but_not_counted_as_linked(tmp_path):
    assert orphans(tmp_path, {"inbox/capture.md": "loose idea\n"}) == []
    v = vault(tmp_path / "x", {**PAIR, "inbox/capture.md": "loose idea\n"})
    notes, deg = ring.analyze(v)
    assert deg["inbox/capture.md"] == 0


def test_link_coming_from_the_inbox_counts_as_an_edge(tmp_path):
    assert orphans(tmp_path, {"target.md": "x\n", "inbox/c.md": "goes [[target]]\n"}) == []


def test_plugin_task_without_a_project_is_exempt_but_links_what_it_points_to(tmp_path):
    """The TaskNotes plugin creates the task in the interface, without asking for a link: blocking that at commit would make
    people uninstall, as with the inbox. But a link leaving the task still counts as an edge."""
    assert orphans(tmp_path, {"tasks/buy-batteries.md": "---\ntags:\n  - task\n---\n"}) == []
    assert orphans(tmp_path, {"target.md": "x\n", "tasks/t.md": "---\nprojects:\n  - \"[[target]]\"\n---\n"}) == []
    v = vault(tmp_path / "x", {**PAIR, "tasks/buy-batteries.md": "---\ntags:\n  - task\n---\n"})
    notes, deg = ring.analyze(v)
    assert deg["tasks/buy-batteries.md"] == 0


def test_only_tasks_at_the_root_is_exempt_not_a_similar_name(tmp_path):
    # "tasks-old" STARTS with "tasks": only the exact folder, not the prefix, is exempt
    assert orphans(tmp_path, {"notes/tasks/x.md": "x\n", "tasks-old/y.md": "y\n"}) == [
        "notes/tasks/x.md", "tasks-old/y.md"]


def test_outside_the_inbox_with_a_similar_name_is_not_exempt(tmp_path):
    # "inbox-old" STARTS with "inbox": only the exact folder, not the prefix, is exempt
    assert orphans(tmp_path, {"inbox-old/x.md": "x\n", "notes/inbox/y.md": "y\n"}) == [
        "inbox-old/x.md", "notes/inbox/y.md"]


# ---- gate --------------------------------------------------------------------

def gate(v, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--gate", *args],
                          capture_output=True, text=True)


def test_gate_fails_an_orphan_and_teaches_the_fix(tmp_path):
    v = vault(tmp_path, {**PAIR, "loose.md": "nothing\n"})
    r = gate(v)
    assert r.returncode == 1 and "loose.md" in r.stdout
    for hint in ("How to fix", "[[", "inbox/", "--no-verify"):
        assert hint in r.stdout


def test_gate_cure_and_pass(tmp_path):
    v = vault(tmp_path, {**PAIR, "loose.md": "nothing\n"})
    assert gate(v).returncode == 1
    (v / "loose.md").write_text("now links to [[a]]\n", encoding="utf-8")
    assert gate(v).returncode == 0


def test_gate_missing_vault_does_not_say_ok(tmp_path):
    r = gate(tmp_path / "does-not-exist")
    assert r.returncode == 2 and "OK" not in r.stdout


# ---- vault/gate.txt: orphan: block | warn ---------------------------------------

LOOSE = {**PAIR, "loose.md": "nothing\n"}


def test_default_without_gate_txt_blocks(tmp_path):
    r = gate(vault(tmp_path, LOOSE))
    assert r.returncode == 1 and "FAILS" in r.stdout


def test_gate_txt_block_blocks(tmp_path):
    r = gate(vault(tmp_path, {**LOOSE, "gate.txt": "# c\norphan: block\n"}))
    assert r.returncode == 1 and "loose.md" in r.stdout


def test_gate_txt_warn_passes_and_prints_the_same_report_as_warning(tmp_path):
    r = gate(vault(tmp_path, {**LOOSE, "gate.txt": "# c\norphan: warn  # trailing comment\n"}))
    assert r.returncode == 0 and "WARNING" in r.stdout and "loose.md" in r.stdout and "FAILS" not in r.stdout


def test_gate_txt_warn_with_no_orphan_is_ok(tmp_path):
    r = gate(vault(tmp_path, {**PAIR, "gate.txt": "orphan: warn\n"}))
    assert r.returncode == 0 and r.stdout.startswith("OK")


def test_gate_txt_with_only_comments_means_block(tmp_path):
    assert gate(vault(tmp_path, {**LOOSE, "gate.txt": "# nothing set\n\n"})).returncode == 1


@pytest.mark.parametrize("text", ["orphan: sometimes\n", "orphan:\n", "orphan\n", "orphan: \n", "color: warn\n",
                                  "orphan: WARN\n"])
def test_malformed_gate_txt_is_rc_2_even_with_no_orphan(tmp_path, text):
    r = gate(vault(tmp_path, {**PAIR, "gate.txt": text}))
    assert r.returncode == 2 and "ERROR" in r.stdout and "OK" not in r.stdout.replace("ERROR", "")


def test_unreadable_gate_txt_is_rc_2(tmp_path):
    v = vault(tmp_path, PAIR)
    (v / "gate.txt").write_bytes(b"\xff\xfe orphan: warn\n")
    r = gate(v)
    assert r.returncode == 2 and "cannot be read" in r.stdout


def test_warn_in_stage_mode_reports_the_orphan_in_the_commit_and_passes(tmp_path):
    v = vault(tmp_path, {**LOOSE, "gate.txt": "orphan: warn\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "loose.md")
    r = gate(v, "--stage")
    assert r.returncode == 0 and "WARNING" in r.stdout and "loose.md" in r.stdout


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


def test_stage_only_fails_what_is_in_the_commit(tmp_path):
    v = vault(tmp_path, {**PAIR, "in-commit.md": "x\n", "outside.md": "y\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "in-commit.md")
    r = gate(v, "--stage")
    assert r.returncode == 1 and "in-commit.md" in r.stdout
    assert "WARNING" in r.stdout and "outside.md" in r.stdout
    git(tmp_path, "reset", "-q")
    git(tmp_path, "add", "a.md")
    r = gate(v, "--stage")
    assert r.returncode == 0 and "WARNING" in r.stdout and "outside.md" in r.stdout


def test_stage_works_with_a_vault_in_a_subfolder_and_an_accent(tmp_path):
    v = vault(tmp_path / "vault", {**PAIR, "notes/ação.md": "x\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "vault/notes/ação.md")
    assert gate(v, "--stage").returncode == 1


def test_stage_outside_a_git_repo_is_not_verified_never_ok(tmp_path):
    v = vault(tmp_path, {**PAIR, "loose.md": "x\n"})
    r = gate(v, "--stage")
    assert r.returncode == 2 and "NOT_VERIFIED" in r.stdout


def test_cli_json(tmp_path):
    v = vault(tmp_path, {**PAIR, "loose.md": "x\n", "inbox/i.md": "y\n"})
    d = json.loads(subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--json"],
                                  capture_output=True, text=True).stdout)
    assert d == {"total": 4, "orphans": ["loose.md"], "exempt": ["inbox/i.md"]}


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "SELFTEST OK" in r.stdout


def test_edge_goes_to_the_note_in_the_same_folder_and_the_other_stays_an_orphan(tmp_path):
    v = vault(tmp_path, {"x/a.md": "goes [[b]]\n", "x/b.md": "x\n", "y/b.md": "y\n"})
    notes, deg = ring.analyze(v)
    assert ring.chk_orphans(notes, deg) == ["y/b.md"]


def test_stage_with_an_nfd_name_matches_what_git_returns(tmp_path):
    import unicodedata
    name = unicodedata.normalize("NFD", "ação.md")
    v = vault(tmp_path, {**PAIR, name: "x\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", name)
    assert gate(v, "--stage").returncode == 1


def test_selftest_fails_when_the_gate_lies(monkeypatch, capsys):
    monkeypatch.setattr(ring, "gate", lambda *a, **k: 0)   # a gate that always says OK
    assert ring.selftest() == 1
    assert "FAILED" in capsys.readouterr().out
