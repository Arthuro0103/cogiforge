"""The Claude Code plugin layer: manifest, marketplace and the two entry skills.

The whole repo is the plugin. Only `plugin-skills/` loads as plugin skills; the 17 working skills stay in
`.claude/skills/` and travel inside each workbench. These tests read the files, they do not install anything.
The version of plugin.json is written in the README section about the plugin (and nowhere else is it checked).
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
ENTRY = ["cf-new-workbench", "cf-adopt"]


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_plugin_json_has_the_required_fields():
    m = load(PLUGIN)
    assert m["name"] == "cogiforge" and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", m["name"])
    assert not m["name"].startswith("claude-")
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"])
    for k in ("displayName", "description", "homepage", "repository", "license", "keywords"):
        assert m.get(k), k
    assert m["author"]["name"]
    assert m["skills"].startswith("./") and (ROOT / m["skills"]).is_dir()


def test_marketplace_json_has_the_required_fields_and_points_at_the_root():
    m = load(MARKET)
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", m["name"]) and ".." not in m["name"]
    assert not m["name"].startswith("claude-") and not m["name"].startswith("claudeai-")
    assert m["owner"]["name"]
    assert len(m["plugins"]) == 1
    e = m["plugins"][0]
    assert e["name"] == load(PLUGIN)["name"]
    assert e["source"] in ("./", ".")
    assert (ROOT / e["source"] / ".claude-plugin" / "plugin.json").is_file()


def test_only_the_two_entry_skills_are_plugin_skills():
    found = sorted(p.name for p in (ROOT / "plugin-skills").iterdir() if p.is_dir())
    assert found == sorted(ENTRY)
    assert not (ROOT / "skills").exists()   # the default scan folder must stay empty: the 17 are not plugin skills


@pytest.mark.parametrize("name", ENTRY)
def test_entry_skills_use_the_plugin_root_variable(name):
    body = (ROOT / "plugin-skills" / name / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" in body
    # a relative `python3 tools/...` would run in the user's folder, not in the plugin
    assert not re.search(r"python3 (\./)?tools/", body)
    # the exclusion list of the copy is written down
    assert ".claude-plugin" in body and "plugin-skills" in body


def test_adopt_runs_from_the_stable_copy():
    body = (ROOT / "plugin-skills" / "cf-adopt" / "SKILL.md").read_text(encoding="utf-8")
    assert "~/.cogiforge/tools/adopt.py" in body


def test_new_workbench_never_overwrites_and_never_skips_the_gate():
    body = (ROOT / "plugin-skills" / "cf-new-workbench" / "SKILL.md").read_text(encoding="utf-8")
    assert "Never overwrite" in body and "--no-verify" in body and "install.sh" in body


def test_the_version_is_in_the_readme_plugin_section():
    v = load(PLUGIN)["version"]
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("## Install as a Claude Code plugin")
    end = text.find("\n## ", start + 1)
    assert v in text[start:end]
    assert f"workbench from cogiforge {v}" in (ROOT / "plugin-skills" / "cf-new-workbench" / "SKILL.md").read_text(encoding="utf-8")
