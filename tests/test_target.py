"""target.py: a NEW note under notes/ says what it is for. It warns by default and blocks only if gate.txt says so."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "core" / "target.py"
NO_TARGET = "---\ntype: note\narea: life\n---\n# A note\n\nbody [[home]]\n"
WITH_NONE = NO_TARGET.replace("area: life\n", "area: life\ntarget: none\n")
WITH_PATH = NO_TARGET.replace("area: life\n", "area: life\ntarget: projects/p/instructions.md\n")


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "vault").mkdir()
    (tmp_path / "vault/home.md").write_text("home\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def put(repo, rel, text, stage=True):
    p = repo / "vault" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if stage:
        git(repo, "add", f"vault/{rel}")


def target(repo):
    return subprocess.run([sys.executable, str(SCRIPT), "--vault", str(repo / "vault"), "--staged"], capture_output=True, text=True)


def test_a_new_note_without_target_warns_and_does_not_block(repo):
    put(repo, "notes/life/n.md", NO_TARGET)
    r = target(repo)
    assert r.returncode == 0 and "WARNING" in r.stdout and "notes/life/n.md" in r.stdout and "does not block" in r.stdout
    assert "target: none" in r.stdout  # it teaches the way out


@pytest.mark.parametrize("text", [WITH_NONE, WITH_PATH])
def test_a_new_note_with_a_target_is_ok(repo, text):
    put(repo, "notes/life/n.md", text)
    r = target(repo)
    assert r.returncode == 0 and "WARNING" not in r.stdout and "OK" in r.stdout


def test_an_empty_target_field_counts_as_missing(repo):
    put(repo, "notes/life/n.md", NO_TARGET.replace("area: life\n", "area: life\ntarget:\n"))
    assert "n.md" in target(repo).stdout


def test_a_note_without_frontmatter_is_missing_its_target(repo):
    put(repo, "notes/life/n.md", "# bare\n\nbody\n")
    assert "n.md" in target(repo).stdout


def test_an_edited_old_note_is_not_asked(repo):
    put(repo, "notes/life/old.md", NO_TARGET, stage=True)
    git(repo, "commit", "-q", "-m", "old")
    put(repo, "notes/life/old.md", NO_TARGET + "\nmore\n")
    r = target(repo)
    assert "WARNING" not in r.stdout and "0 new note(s)" in r.stdout


@pytest.mark.parametrize("rel", ["inbox/capture.md", "tasks/t.md", "projects/p/brief.md", "memory/x.md"])
def test_only_notes_are_asked(repo, rel):
    put(repo, rel, "# no target here\n")
    assert "WARNING" not in target(repo).stdout


def test_mode_block_turns_the_same_report_into_a_failure(repo):
    put(repo, "gate.txt", "orphan: block\ntarget: block\n")
    put(repo, "notes/life/n.md", NO_TARGET)
    r = target(repo)
    assert r.returncode == 1 and "FAILS" in r.stdout and "WARNING" not in r.stdout and "does not block" not in r.stdout


def test_mode_warn_written_out_is_the_default(repo):
    put(repo, "gate.txt", "target: warn\n")
    put(repo, "notes/life/n.md", NO_TARGET)
    assert target(repo).returncode == 0


def test_an_unknown_mode_is_rc_2_and_judges_nothing(repo):
    put(repo, "gate.txt", "target: sometimes\n")
    put(repo, "notes/life/n.md", NO_TARGET)
    r = target(repo)
    assert r.returncode == 2 and "sometimes" in r.stdout


def test_an_unreadable_gate_txt_is_rc_2(repo):
    (repo / "vault/gate.txt").write_bytes(b"\xff\xfe\x00bad")
    put(repo, "notes/life/n.md", NO_TARGET)
    assert target(repo).returncode == 2


def test_orphan_lines_in_gate_txt_are_not_this_checks_business(repo):
    put(repo, "gate.txt", "# comment\norphan: warn\n")
    put(repo, "notes/life/n.md", NO_TARGET)
    assert target(repo).returncode == 0


def test_a_missing_vault_is_not_verified_never_ok(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(tmp_path / "none"), "--staged"], capture_output=True, text=True)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout and "OK" not in r.stdout


def test_outside_a_git_repo_is_not_verified_never_ok(tmp_path):
    (tmp_path / "vault").mkdir()
    r = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(tmp_path / "vault"), "--staged"], capture_output=True, text=True,
                       env={"GIT_CEILING_DIRECTORIES": str(tmp_path.parent), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_a_decomposed_file_name_from_git_is_reported_composed(repo):
    import unicodedata
    git(repo, "config", "core.precomposeunicode", "false")  # git keeps the name as the file system spelled it
    rel = "notes/life/" + unicodedata.normalize("NFD", "caf\u00e9") + ".md"
    assert rel != unicodedata.normalize("NFC", rel)
    put(repo, rel, NO_TARGET)
    out = target(repo).stdout
    assert unicodedata.normalize("NFC", rel) in out and rel not in out


def test_the_report_teaches_the_way_out(repo):
    put(repo, "notes/life/n.md", NO_TARGET)
    out = target(repo).stdout
    assert "How to fix: add `target:` to the frontmatter" in out


def test_an_accented_file_name_is_found(repo):
    put(repo, "notes/life/café.md", NO_TARGET)
    assert "café.md" in target(repo).stdout


def test_real_path_finds_a_decomposed_name_when_the_lookup_is_exact(tmp_path):
    # Linux looks names up byte for byte: the report says NFC, the file kept the NFD spelling git gave it.
    import sys, unicodedata
    sys.path.insert(0, str(SCRIPT.parent))
    import target as t
    nfd = unicodedata.normalize("NFD", "café") + ".md"
    nfc = unicodedata.normalize("NFC", nfd)
    assert nfd != nfc
    on_disk = {"notes", "notes/life", "notes/life/" + nfd}

    def exists(p):  # exact, as on Linux
        return str(p).replace(str(tmp_path) + "/", "").replace(str(tmp_path), "") in on_disk or str(p) == str(tmp_path)

    def entries(d):
        base = str(d).replace(str(tmp_path), "").lstrip("/")
        pre = base + "/" if base else ""
        return sorted({k[len(pre):].split("/")[0] for k in on_disk if k.startswith(pre) and k != base})

    got = t.real_path(tmp_path, "notes/life/" + nfc, exists=exists, entries=entries)
    assert got == tmp_path / "notes" / "life" / nfd
