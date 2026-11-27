"""No draft marker ships.

A marker such as `@@N10K@@` holds the place of a number that has not been measured yet. WHY.md was
published with two of them. This test reads every tracked `.md` file, except the test fixtures
(`demo/` and `tests/`), and fails on any marker left in one.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = re.compile(r"@@[A-Z0-9_]+@@")
FIXTURES = ("demo/", "tests/")


def markdown_files(root):
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, encoding="utf-8", cwd=root,
                         check=True).stdout
    return [p for p in out.split("\0")
            if p.lower().endswith(".md") and not p.startswith(FIXTURES) and (root / p).is_file()]


def draft_markers(root):
    """(number of files read, ["path:line: marker"]) for the tracked Markdown under `root`."""
    files, found = markdown_files(root), []
    for rel in files:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            found += [f"{rel}:{n}: {m}" for m in MARKER.findall(line)]
    return len(files), found


def test_no_draft_marker_in_any_tracked_markdown():
    read, found = draft_markers(ROOT)
    assert read, "NOT_VERIFIED: no tracked .md file was read"
    assert not found, "draft marker left in the docs (measure the value and write it):\n" + "\n".join(found)


def test_a_planted_marker_is_found_and_only_outside_the_fixtures(tmp_path):
    for rel in ("docs/a.md", "demo/b.md", "tests/c.md", "d.txt", "untracked.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("fine\nit took @@PRE_2@@ in the hook\n", encoding="utf-8")
    (tmp_path / "plain.md").write_text("a diff header @@ -1,2 +1,2 @@ and @@lower@@ are not markers\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "docs", "demo", "tests", "d.txt", "plain.md"], cwd=tmp_path, check=True)
    assert draft_markers(tmp_path) == (2, ["docs/a.md:2: @@PRE_2@@"])
