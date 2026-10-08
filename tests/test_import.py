"""Paired tests for tools/import.py. IMPORT_PATH points to another copy (used by mutation).

Every test builds a small source folder and a temporary vault, and runs the real command line.
"""
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
IMPORT = os.environ.get("IMPORT_PATH") or str(ROOT / "tools" / "import.py")
REPORT = "_import-report.md"
EMAIL = "bob" + "@" + "corp-real.io"  # assembled here so this file does not trip the leak scan of the repo


def build(base, files):
    for rel, content in files.items():
        p = Path(base) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return Path(base)


def run_import(vault, *args, docling=False, extra_env=None):
    env = {**os.environ, "LEAK_BLOCKLIST": str(Path(vault) / "absent-on-purpose.txt"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    if docling:
        env.pop("COGIFORGE_IMPORT_NO_DOCLING", None)
    else:
        env["COGIFORGE_IMPORT_NO_DOCLING"] = "1"
    env.update(extra_env or {})
    return subprocess.run([sys.executable, IMPORT, *map(str, args), "--vault", str(Path(vault) / "vault")],
                          capture_output=True, text=True, env=env)


def dest_of(vault, name="src"):
    return Path(vault) / "vault" / "inbox" / "imported" / name


def setup(tmp_path, files, name="src"):
    src = build(tmp_path / name, files)
    (tmp_path / "vault" / "inbox").mkdir(parents=True, exist_ok=True)
    return src


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


def load_module():
    spec = importlib.util.spec_from_file_location("import_tool", IMPORT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MINI = {
    "a.md": "# A\n\nlinks to [[sub/b]] and [[missing]]\n",
    "sub/b.md": "# B\n",
    "page.html": "<html><head><title>T</title><script>var x=1;</script></head><body><h1>Head</h1>"
                 "<p>one <a href='x.md'>two</a></p><ul><li>i</li><li>j</li></ul></body></html>",
    "t.csv": "a,b\n1,2\n",
    "d.json": '{"k": 1}',
    "doc.pdf": b"%PDF-1.4 fake",
    "img/p.png": b"\x89PNG fake",
    ".obsidian/app.json": "{}",
    ".obsidian/plugins/x.js": "x",
    ".hidden": "h",
}


# ---------------------------------------------------------------- the formats

def test_markdown_is_copied_byte_for_byte_and_a_txt_becomes_markdown(tmp_path):
    odd = "# Title\r\n\r\ntab\there  trailing  \n\n[[x|y]] ```not a fence\n".encode("utf-8")
    setup(tmp_path, {"n.md": odd, "plain.txt": "just text\n"})
    r = run_import(tmp_path, tmp_path / "src")
    assert r.returncode == 0, r.stdout + r.stderr
    d = dest_of(tmp_path)
    assert (d / "n.md").read_bytes() == odd
    assert (d / "plain.md").read_text() == "just text\n"
    assert not (d / "plain.txt").exists()


def test_html_becomes_markdown_and_script_text_is_dropped(tmp_path):
    setup(tmp_path, {"page.html": MINI["page.html"]})
    run_import(tmp_path, tmp_path / "src")
    text = (dest_of(tmp_path) / "page.md").read_text()
    assert "# Head" in text and "[two](x.md)" in text and "- i\n- j" in text
    assert "var x" not in text and "<p>" not in text


def test_html_code_block_and_inline_code_and_table(tmp_path):
    html = "<p>use <code>ls</code></p><pre>a\n  b</pre><table><tr><th>h1</th><th>h2</th></tr><tr><td>1</td><td>2</td></tr></table>"
    setup(tmp_path, {"c.html": html})
    run_import(tmp_path, tmp_path / "src")
    text = (dest_of(tmp_path) / "c.md").read_text()
    assert "use `ls`" in text and "```\na\n  b\n```" in text
    assert "| h1 | h2 |\n| --- | --- |\n| 1 | 2 |" in text


def test_csv_becomes_a_table_and_a_pipe_is_escaped(tmp_path):
    setup(tmp_path, {"t.csv": "name,note\nx,a|b\ny,2\n"})
    run_import(tmp_path, tmp_path / "src")
    text = (dest_of(tmp_path) / "t.md").read_text()
    assert text.splitlines()[0] == "| name | note |"
    assert text.splitlines()[1] == "| --- | --- |"
    assert "| x | a\\|b |" in text


def test_json_becomes_a_fenced_block_and_an_image_is_copied_as_is(tmp_path):
    png = b"\x89PNG\r\n\x1a\n\x00\x01"
    setup(tmp_path, {"d.json": '{"k": [1, 2]}', "img/deep/p.png": png})
    run_import(tmp_path, tmp_path / "src")
    d = dest_of(tmp_path)
    assert (d / "d.md").read_text() == '```json\n{"k": [1, 2]}\n```\n'
    assert (d / "img" / "deep" / "p.png").read_bytes() == png


def test_pdf_without_docling_goes_to_unconverted_and_is_in_the_report(tmp_path):
    setup(tmp_path, {"report.pdf": b"%PDF fake", "ok.md": "# ok\n"})
    r = run_import(tmp_path, tmp_path / "src")
    d = dest_of(tmp_path)
    assert r.returncode == 1
    assert (d / "_unconverted" / "report.pdf").read_bytes() == b"%PDF fake"
    report = (d / REPORT).read_text()
    assert "report.pdf" in report and "pip install docling" in report and "not installed" in report


def test_pdf_with_docling_is_converted_instead(tmp_path):
    fake = tmp_path / "fake" / "docling"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("")
    (fake / "document_converter.py").write_text(
        "class _D:\n    def export_to_markdown(self):\n        return '# converted by fake\\n'\n"
        "class _R:\n    document = _D()\n"
        "class DocumentConverter:\n    def convert(self, path):\n        return _R()\n")
    setup(tmp_path, {"report.pdf": b"%PDF fake"})
    r = run_import(tmp_path, tmp_path / "src", docling=True, extra_env={"PYTHONPATH": str(tmp_path / "fake")})
    d = dest_of(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (d / "report.md").read_text() == "# converted by fake\n"
    assert not (d / "_unconverted").exists()


def test_unknown_extension_is_copied_to_unconverted_with_a_reason(tmp_path):
    setup(tmp_path, {"bundle.zip": b"PK\x03\x04"})
    r = run_import(tmp_path, tmp_path / "src")
    assert r.returncode == 1
    assert (dest_of(tmp_path) / "_unconverted" / "bundle.zip").is_file()
    assert "no converter" in (dest_of(tmp_path) / REPORT).read_text()


# ---------------------------------------------------------------- nothing is lost in silence

def test_every_file_of_the_source_is_in_the_report_and_the_count_closes(tmp_path):
    src = setup(tmp_path, MINI)
    run_import(tmp_path, src)
    report = (dest_of(tmp_path) / REPORT).read_text()
    found = [p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()]
    assert len(found) == 10
    for rel in found:
        assert f"`{rel}`" in report, f"{rel} is not in the report"
    assert "| in the source | 10 |" in report
    nums = [int(n) for n in re.findall(r"^\| (?:converted|copied|unchanged|ignored|unconverted|skipped) \| (\d+) \|",
                                       report, re.M)]
    assert len(nums) == 6 and sum(nums) == len(found)


def test_obsidian_hidden_and_node_modules_are_ignored_but_listed(tmp_path):
    files = {**MINI, "node_modules/pkg/readme.md": "# lib\n", "__pycache__/x.pyc": b"\x00"}
    src = setup(tmp_path, files)
    run_import(tmp_path, src)
    d = dest_of(tmp_path)
    assert not (d / ".obsidian").exists() and not (d / ".hidden").exists()
    assert not (d / "node_modules").exists() and not (d / "__pycache__").exists()
    report = (d / REPORT).read_text()
    assert "`.obsidian/app.json`" in report and "`node_modules/pkg/readme.md`" in report
    assert "hidden file" in report


def test_a_note_in_a_normal_folder_is_not_ignored(tmp_path):
    setup(tmp_path, {"obsidian-notes/a.md": "# a\n", "my.obsidian.md": "# b\n"})
    run_import(tmp_path, tmp_path / "src")
    d = dest_of(tmp_path)
    assert (d / "obsidian-notes" / "a.md").is_file() and (d / "my.obsidian.md").is_file()


def test_symlink_is_skipped_never_followed_and_listed(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("# outside\n")
    src = setup(tmp_path, {"a.md": "# a\n"})
    os.symlink(outside, src / "link.md")
    r = run_import(tmp_path, src)
    assert r.returncode == 1
    assert not (dest_of(tmp_path) / "link.md").exists()
    assert "symlink" in (dest_of(tmp_path) / REPORT).read_text()


def test_dataless_file_is_skipped_and_registered_never_copied_as_zero_bytes(tmp_path):
    mod = load_module()
    src = build(tmp_path / "src", {"cloud.md": "# real\n", "local.md": "# local\n"})
    real_is = mod.is_dataless
    mod.is_dataless = lambda st: st.st_size == 7  # "# real\n" is 7 bytes, "# local\n" is 8
    try:
        entries = mod.import_tree(src, tmp_path / "out", dry=False)
    finally:
        mod.is_dataless = real_is
    cats = {e["src"]: e["cat"] for e in entries}
    assert cats == {"cloud.md": "skipped", "local.md": "copied"}
    assert not (tmp_path / "out" / "cloud.md").exists()
    assert "dataless" in [e for e in entries if e["cat"] == "skipped"][0]["reason"]


def test_dataless_detection_is_exact():
    mod = load_module()

    class St:
        def __init__(self, size, blocks):
            self.st_size, self.st_blocks = size, blocks

    assert mod.is_dataless(St(100, 0)) is True
    assert mod.is_dataless(St(100, 8)) is False
    assert mod.is_dataless(St(0, 0)) is False  # an empty file legitimately has no blocks


@pytest.mark.skipif(sys.platform == "win32", reason="chmod(0) cannot make a file unreadable on Windows (POSIX permission bits)")
def test_unreadable_file_is_skipped_and_registered(tmp_path):
    if os.geteuid() == 0:
        return  # root reads everything: the situation cannot be built
    src = setup(tmp_path, {"a.md": "# a\n", "locked.md": "# locked\n"})
    os.chmod(src / "locked.md", 0)
    try:
        r = run_import(tmp_path, src)
    finally:
        os.chmod(src / "locked.md", 0o600)
    assert r.returncode == 1
    assert not (dest_of(tmp_path) / "locked.md").exists()
    assert "locked.md" in (dest_of(tmp_path) / REPORT).read_text()


# ---------------------------------------------------------------- names, collisions, reruns

def test_names_are_normalized_to_nfc(tmp_path):
    nfd, nfc = "cafe\u0301.md", "caf\u00e9.md"
    setup(tmp_path, {nfd: "# c\n"})
    run_import(tmp_path, tmp_path / "src")
    names = {os.path.basename(str(p)) for p in dest_of(tmp_path).iterdir()}
    import unicodedata
    assert {unicodedata.normalize("NFC", n) for n in names} >= {nfc}
    assert nfd not in names or nfc in names
    assert all(unicodedata.is_normalized("NFC", n) for n in names)


def test_second_run_is_idempotent(tmp_path):
    src = setup(tmp_path, MINI)
    run_import(tmp_path, src)
    first = {k: v for k, v in tree(dest_of(tmp_path)).items() if k != REPORT}
    r = run_import(tmp_path, src)
    second = {k: v for k, v in tree(dest_of(tmp_path)).items() if k != REPORT}
    assert first == second
    report = (dest_of(tmp_path) / REPORT).read_text()
    assert "| unchanged | 6 |" in report and "| converted | 0 |" in report and "| copied | 0 |" in report
    assert r.returncode == 1  # the pdf is still not converted: that is still true


def test_a_changed_source_is_not_called_unchanged(tmp_path):
    src = setup(tmp_path, {"a.md": "# one\n"})
    run_import(tmp_path, src)
    (src / "a.md").write_text("# two\n")
    run_import(tmp_path, src)
    assert "| unchanged | 0 |" in (dest_of(tmp_path) / REPORT).read_text()


def test_name_collision_with_different_content_never_overwrites(tmp_path):
    src = setup(tmp_path, {"a.md": "# first\n"})
    run_import(tmp_path, src)
    (src / "a.md").write_text("# second\n")
    run_import(tmp_path, src)
    d = dest_of(tmp_path)
    assert (d / "a.md").read_text() == "# first\n"
    extra = [p for p in d.glob("a.*.md")]
    assert len(extra) == 1 and extra[0].read_text() == "# second\n"
    assert "Name collisions (1)" in (d / REPORT).read_text()
    run_import(tmp_path, src)  # and the rerun does not pile up a third file
    assert len(list(d.glob("a.*.md"))) == 1


def test_txt_and_md_with_the_same_stem_do_not_overwrite_each_other(tmp_path):
    setup(tmp_path, {"n.md": "# md\n", "n.txt": "text\n"})
    run_import(tmp_path, tmp_path / "src")
    d = dest_of(tmp_path)
    assert (d / "n.md").read_text() == "# md\n"
    assert len(list(d.glob("n.*.md"))) == 1
    assert any(p.read_text() == "text\n" for p in d.glob("n.*.md"))


# ---------------------------------------------------------------- dry run, empty, person, destination

def test_dry_run_writes_nothing_and_still_prints_the_report(tmp_path):
    src = setup(tmp_path, MINI)
    before = tree(tmp_path / "vault")
    r = run_import(tmp_path, src, "--dry-run", "--report", tmp_path / "r.md")
    assert r.returncode == 1
    assert tree(tmp_path / "vault") == before
    assert not (tmp_path / "r.md").exists() and not dest_of(tmp_path).exists()
    assert "Dry run" in r.stdout and "page.html" in r.stdout


def test_without_dry_run_the_same_command_writes(tmp_path):
    src = setup(tmp_path, MINI)
    run_import(tmp_path, src, "--report", tmp_path / "r.md")
    assert (tmp_path / "r.md").is_file() and (dest_of(tmp_path) / "page.md").is_file()


def test_empty_folder_says_nothing_to_import_and_never_ok(tmp_path):
    (tmp_path / "empty").mkdir()
    (tmp_path / "vault" / "inbox").mkdir(parents=True)
    r = run_import(tmp_path, tmp_path / "empty")
    assert "nothing to import" in r.stdout
    assert "OK" not in r.stdout.upper().replace("NOTHING", "")
    assert not dest_of(tmp_path, "empty").exists()


def test_a_folder_with_only_ignored_files_also_says_nothing_to_import(tmp_path):
    setup(tmp_path, {".obsidian/app.json": "{}", ".DS_Store": b"x"})
    r = run_import(tmp_path, tmp_path / "src")
    assert "nothing to import" in r.stdout and "2 ignored" in r.stdout
    assert not dest_of(tmp_path).exists()


def test_a_folder_with_something_does_not_say_nothing_to_import(tmp_path):
    setup(tmp_path, {"a.md": "# a\n"})
    r = run_import(tmp_path, tmp_path / "src")
    assert "nothing to import" not in r.stdout and r.returncode == 0


def test_person_that_does_not_exist_is_rc_2_and_writes_nothing(tmp_path):
    setup(tmp_path, {"a.md": "# a\n"})
    r = run_import(tmp_path, tmp_path / "src", "--person", "ghost")
    assert r.returncode == 2 and "ghost" in r.stderr
    assert not (tmp_path / "vault" / "people").exists() and not dest_of(tmp_path).exists()


def test_person_that_exists_changes_the_default_destination(tmp_path):
    setup(tmp_path, {"a.md": "# a\n"})
    (tmp_path / "vault" / "people" / "ana").mkdir(parents=True)
    r = run_import(tmp_path, tmp_path / "src", "--person", "ana")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "vault" / "people" / "ana" / "inbox" / "imported" / "src" / "a.md").is_file()
    assert not dest_of(tmp_path).exists()


def test_person_handle_cannot_walk_out_of_the_people_folder(tmp_path):
    setup(tmp_path, {"a.md": "# a\n"})
    (tmp_path / "vault" / "secret").mkdir(parents=True)
    r = run_import(tmp_path, tmp_path / "src", "--person", "../secret")
    assert r.returncode == 2
    assert not (tmp_path / "vault" / "secret" / "inbox").exists()


def test_missing_source_is_rc_3_and_destination_inside_source_is_rc_2(tmp_path):
    (tmp_path / "vault" / "inbox").mkdir(parents=True)
    assert run_import(tmp_path, tmp_path / "nope").returncode == 3
    src = setup(tmp_path, {"a.md": "# a\n"})
    r = run_import(tmp_path, src, "--dest", src / "out")
    assert r.returncode == 2 and not (src / "out").exists()


# ---------------------------------------------------------------- leaks

def test_planted_leak_is_in_the_report_without_the_data_and_warns_about_the_commit(tmp_path):
    setup(tmp_path, {"people.md": f"# Team\n\nwrite to {EMAIL} please\n", "clean.md": "# clean\n"})
    r = run_import(tmp_path, tmp_path / "src")
    d = dest_of(tmp_path)
    report = (d / REPORT).read_text()
    assert r.returncode == 1
    assert "people.md:3:email" in report
    assert EMAIL not in report and EMAIL not in r.stdout + r.stderr and "corp-real" not in report
    assert "BLOCK the commit" in report and "WARNING" in r.stdout
    assert (d / "people.md").read_text().count(EMAIL) == 1  # the copy was not stopped


def test_without_a_leak_there_is_no_warning(tmp_path):
    setup(tmp_path, {"clean.md": "# clean\n"})
    r = run_import(tmp_path, tmp_path / "src")
    report = (dest_of(tmp_path) / REPORT).read_text()
    assert r.returncode == 0 and "BLOCK" not in report and "WARNING" not in r.stdout


def test_the_report_never_carries_a_machine_path(tmp_path):
    src = setup(tmp_path, MINI)
    r = run_import(tmp_path, src)
    report = (dest_of(tmp_path) / REPORT).read_text()
    assert str(tmp_path) not in report and "/Users/" not in report and str(Path.home()) not in report
    assert "NOT_VERIFIED" in report  # the private list is absent in this test, and the report says so
    assert str(Path.home()) not in r.stdout


# ---------------------------------------------------------------- the ring

def ring(vault):
    return subprocess.run([sys.executable, str(ROOT / "core" / "ring.py"), "--vault", str(Path(vault) / "vault"),
                           "--gate"], capture_output=True, text=True)


def test_imported_notes_in_the_inbox_are_not_orphans_for_the_ring(tmp_path):
    setup(tmp_path, {"loose.md": "# loose\n\nlinks to nothing\n"})
    run_import(tmp_path, tmp_path / "src")
    assert (dest_of(tmp_path) / "loose.md").is_file()
    r = ring(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_same_note_outside_the_inbox_is_an_orphan(tmp_path):
    setup(tmp_path, {"loose.md": "# loose\n\nlinks to nothing\n"})
    run_import(tmp_path, tmp_path / "src", "--dest", tmp_path / "vault" / "notes" / "imported")
    r = ring(tmp_path)
    assert r.returncode == 1
    assert "not inside an inbox" in (tmp_path / "vault" / "notes" / "imported" / REPORT).read_text()


# ---------------------------------------------------------------- the tool itself

def test_selftest_passes():
    r = subprocess.run([sys.executable, IMPORT, "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "selftest: OK" in r.stdout


def test_no_source_is_a_usage_error():
    r = subprocess.run([sys.executable, IMPORT], capture_output=True, text=True)
    assert r.returncode == 2
