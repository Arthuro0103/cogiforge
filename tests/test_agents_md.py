"""AGENTS.md is the model-agnostic copy of the rules; CLAUDE.md at the root only points to it."""
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


def test_guides_are_linked_from_the_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for doc in ("AGENTS.md", "docs/EXPORTING-CHATS.md", "docs/RESEARCH.md", "docs/USING-OTHER-MODELS.md"):
        assert doc in readme and (ROOT / doc).is_file(), doc
