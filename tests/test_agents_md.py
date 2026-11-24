"""AGENTS.md is the model-agnostic copy of the rules; CLAUDE.md at the root only points to it."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_agents_md_exists_and_names_the_vault():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "vault/" in text and "target" in text.lower()
    for rule in ("prose-as-title", "never write about the user", "SKILL.md"):
        assert rule.lower() in text.lower(), rule


def test_root_claude_md_stays_small_and_points_to_agents_md():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 5 * 1024
    assert "AGENTS.md" in text


def test_agents_md_does_not_drift_from_claude_md():
    """Every hard rule that CLAUDE.md states must still appear in AGENTS.md."""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
    for phrase in ("only inside `vault/`", "git push", "--no-verify", "not_verified", "graph_report.md", "core/leak.py"):
        assert phrase in agents, phrase


def numbered_rules(path):
    """Rules of the `## The rules` section: a list of the text of each numbered item."""
    text = Path(path).read_text(encoding="utf-8")
    section = re.search(r"^## The rules\n(.*?)(?=^## |\Z)", text, re.S | re.M).group(1)
    items = re.split(r"^\d+\. ", section, flags=re.M)[1:]
    return [i.strip() for i in items]


def is_path_or_command(snippet):
    return any(mark in snippet for mark in ("/", ".py", "--", "::"))


def rules_drift(claude_path, agents_path):
    """Return the list of drift messages between the two `## The rules` lists (empty = in sync)."""
    claude, agents = numbered_rules(claude_path), numbered_rules(agents_path)
    if len(claude) != len(agents):
        return [f"rule count differs: CLAUDE.md has {len(claude)}, AGENTS.md has {len(agents)}"]
    problems = []
    for n, (c, a) in enumerate(zip(claude, agents), start=1):
        for snippet in re.findall(r"`([^`]+)`", c):
            if snippet not in a:
                problems.append(f"rule {n}: `{snippet}` is in CLAUDE.md but missing in AGENTS.md")
        for snippet in re.findall(r"`([^`]+)`", a):
            if is_path_or_command(snippet) and snippet not in c:
                problems.append(f"rule {n}: `{snippet}` is in AGENTS.md but missing in CLAUDE.md")
    return problems


def test_rules_lists_stay_in_sync():
    assert rules_drift(ROOT / "CLAUDE.md", ROOT / "AGENTS.md") == []


def test_rules_drift_check_catches_a_removed_snippet(tmp_path):
    """Test of the test: dropping a backticked snippet from rule 3 in a copy must be reported."""
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    broken = text.replace("`question::`, ", "", 1)
    assert broken != text
    copy = tmp_path / "AGENTS.md"
    copy.write_text(broken, encoding="utf-8")
    problems = rules_drift(ROOT / "CLAUDE.md", copy)
    assert any(p.startswith("rule 3:") and "question::" in p for p in problems), problems


def test_guides_are_linked_from_the_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for doc in ("AGENTS.md", "docs/EXPORTING-CHATS.md", "docs/RESEARCH.md", "docs/USING-OTHER-MODELS.md"):
        assert doc in readme and (ROOT / doc).is_file(), doc
