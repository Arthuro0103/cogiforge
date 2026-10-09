"""Skill names: every skill carries the cf- prefix, the name is valid, and no text cites an old slash-command."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
PREFIX = "cf-"

# The names the 14 skills had before the prefix. Only used to find stale mentions.
OLD_NAMES = [
    "adapt-skill", "adopt", "ask", "brainstorm", "claude-corner", "close-session", "extract-routine",
    "import-knowledge", "know-my-product", "onboard", "open-session", "study", "task-observer", "whats-real",
]
# Skills born after the prefix existed: they never had an old name, so they are not in OLD_NAMES.
NEW_NAMES = ["new-project", "brand"]
TEXT_SUFFIXES = {".md", ".py", ".sh", ".yml", ".yaml", ".svg"}

# A slash-command is a "/" that starts a word: not after a word char, "/", "." or "-" (so paths such as
# tools/ask.py or vault/projects/<name>/whats-real.md do not match), not followed by more name
# characters, and not followed by a file extension.
STALE = re.compile(r"(?<![\w/.-])/(" + "|".join(map(re.escape, OLD_NAMES)) + r")(?![\w-])(?!\.\w)")

# Explicit, justified false positives: {relative path: [exact matched strings]}. Empty on purpose:
# at the time of writing there is none. Add a line only with the reason beside it.
ALLOWLIST = {}


def skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def frontmatter_name(skill_md):
    m = re.match(r"---\n(.*?)\n---\n", skill_md.read_text(encoding="utf-8"), re.S)
    assert m, f"{skill_md}: no frontmatter"
    n = re.search(r"^name: (.+)$", m.group(1), re.M)
    assert n, f"{skill_md}: no name"
    return n.group(1).strip()


def stale_mentions(root, files):
    hits = []
    for rel in files:
        p = Path(root) / rel
        if p.suffix not in TEXT_SUFFIXES or not p.is_file() or rel == "tests/test_skill_names.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in STALE.finditer(line):
                if m.group(0) not in ALLOWLIST.get(rel, []):
                    hits.append(f"{rel}:{i}: {m.group(0)}")
    return hits


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.split("\n") if f]


def test_there_are_sixteen_skills():
    assert len(skill_dirs()) == 16


@pytest.mark.parametrize("d", skill_dirs(), ids=lambda d: d.name)
def test_folder_starts_with_the_prefix(d):
    assert d.name.startswith(PREFIX)


@pytest.mark.parametrize("d", skill_dirs(), ids=lambda d: d.name)
def test_frontmatter_name_equals_the_folder(d):
    assert frontmatter_name(d / "SKILL.md") == d.name


@pytest.mark.parametrize("d", skill_dirs(), ids=lambda d: d.name)
def test_name_follows_the_specification(d):
    n = d.name
    assert re.fullmatch(r"[a-z0-9-]+", n)
    assert len(n) <= 64
    assert "--" not in n
    assert not n.startswith("-") and not n.endswith("-")


def test_the_prefixed_folders_are_the_old_names_plus_the_prefix():
    assert [d.name for d in skill_dirs()] == sorted(PREFIX + n for n in OLD_NAMES + NEW_NAMES)


def test_no_file_cites_a_slash_command_without_the_prefix():
    assert stale_mentions(ROOT, tracked_files()) == []


def test_the_scan_catches_a_planted_old_mention(tmp_path):
    (tmp_path / "doc.md").write_text("Type /onboard to start.\n", encoding="utf-8")
    assert stale_mentions(tmp_path, ["doc.md"]) == ["doc.md:1: /onboard"]


def test_the_scan_ignores_prefixed_commands_paths_and_files(tmp_path):
    (tmp_path / "doc.md").write_text(
        "Type /cf-onboard. Run python3 tools/ask.py, edit vault/projects/<name>/whats-real.md and /tmp/study/x.\n",
        encoding="utf-8")
    assert stale_mentions(tmp_path, ["doc.md"]) == []
