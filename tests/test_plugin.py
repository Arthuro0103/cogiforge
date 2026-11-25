"""The Claude Code plugin layer: manifest, marketplace, the two entry skills and the directory's allow-list.

The plugin is the `plugin/` folder (the marketplace points at it). It carries only Markdown, JSON and the icon:
the Anthropic directory refuses code from organizations that are not verified, so the skills download this repo
from GitHub at the tag of the plugin's version. The 17 working skills stay in `.claude/skills/` and travel
inside each workbench. These tests read the files, they do not install anything.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PDIR = ROOT / "plugin"
PLUGIN = PDIR / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
ENTRY = ["cf-new-workbench", "cf-adopt"]
PLUGIN_KEYS = {"name", "displayName", "version", "description", "author", "homepage", "repository", "license",
               "keywords", "icon"}
MARKET_KEYS = {"name", "description", "owner", "plugins"}
MARKET_ENTRY_KEYS = {"name", "source", "description"}


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def skill(name):
    return (PDIR / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def test_plugin_json_has_the_required_fields():
    m = load(PLUGIN)
    assert set(m) <= PLUGIN_KEYS and "skills" not in m   # the default skills/ folder is enough
    assert m["name"] == "cogiforge" and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", m["name"])
    assert not m["name"].startswith("claude-")
    assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"])
    for k in ("displayName", "description", "homepage", "repository", "license", "keywords"):
        assert m.get(k), k
    assert m["author"]["name"]
    assert m["icon"] == "./icon.svg" and (PDIR / m["icon"]).is_file()


def test_marketplace_points_at_the_plugin_folder():
    m = load(MARKET)
    assert set(m) <= MARKET_KEYS
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", m["name"]) and ".." not in m["name"]
    assert not m["name"].startswith("claude-") and not m["name"].startswith("claudeai-")
    assert m["owner"]["name"]
    assert len(m["plugins"]) == 1
    e = m["plugins"][0]
    assert set(e) <= MARKET_ENTRY_KEYS
    assert e["name"] == load(PLUGIN)["name"]
    assert e["source"] == "./plugin"
    assert (ROOT / e["source"] / ".claude-plugin" / "plugin.json").is_file()
    assert not (ROOT / ".claude-plugin" / "plugin.json").exists()   # the root is no longer the plugin
    assert not (ROOT / "plugin-skills").exists()


def test_only_the_two_entry_skills_are_plugin_skills():
    found = sorted(p.name for p in (PDIR / "skills").iterdir() if p.is_dir())
    assert found == sorted(ENTRY)
    assert not (ROOT / "skills").exists()


@pytest.mark.parametrize("name", ENTRY)
def test_entry_skills_download_the_tag_of_the_plugin_version(name):
    m = load(PLUGIN)
    v, url = m["version"], m["repository"] + ".git"
    body = skill(name)
    assert f"--branch v{v}" in body and url in body
    assert "${CLAUDE_PLUGIN_ROOT}" not in body and ".in_use" not in body
    # every version written in the skill is the plugin's
    for found in re.findall(r"\bv\d+\.\d+\.\d+\b|cogiforge \d+\.\d+\.\d+", body):
        assert found.endswith(v), found


def test_adopt_runs_from_the_stable_copy_and_asks_before_replacing():
    body = skill("cf-adopt")
    assert "~/.cogiforge/tools/adopt.py" in body
    assert "--confirm" in body and "--yes" not in body
    blocks = [b.strip() for b in re.findall(r"```bash\n(.*?)```", body, re.S) if "~/.cogiforge.new" in b]
    assert len(blocks) == 1 and "\n" not in blocks[0]
    parts = [x.strip() for x in blocks[0].split("&&")]
    clone = next(i for i, x in enumerate(parts) if x.startswith("git clone") and "~/.cogiforge.new" in x)
    rm_old = next(i for i, x in enumerate(parts) if x.startswith("rm -rf ~/.cogiforge") and x.split()[-1] == "~/.cogiforge")
    assert clone < rm_old, "the new copy exists before the old one is deleted"


def test_new_workbench_never_overwrites_and_never_skips_the_gate():
    body = skill("cf-new-workbench")
    assert "Never overwrite" in body and "--no-verify" in body and "install.sh" in body
    assert f"workbench from cogiforge {load(PLUGIN)['version']}" in body


def test_new_workbench_deletes_only_after_a_guarded_download():
    blocks = [b for b in re.findall(r"```bash\n(.*?)```", skill("cf-new-workbench"), re.S) if "rm -rf" in b]
    assert len(blocks) == 1
    cmd = blocks[0].strip()
    assert "\n" not in cmd, "the download and the rm must be one command, not two lines"
    guards = ['[ -n "$DEST" ]', '[ "$DEST" != "/" ]', '[ "$DEST" != "$HOME" ]']
    parts = [x.strip() for x in cmd.split("&&")]
    for g in guards:
        assert g in parts, g
    assert any("-z \"$(ls -A \"$DEST\")\"" in x for x in parts), "empty-folder guard"
    clone = next(i for i, x in enumerate(parts) if x.startswith("git clone"))
    rm = next(i for i, x in enumerate(parts) if x.startswith("rm -rf"))
    assert all(parts.index(g) < clone for g in guards), "every guard comes before the download"
    assert clone < rm, "the rm comes after the clone, joined by &&"
    for gone in (".git", "plugin", ".claude-plugin"):
        assert f'"$DEST/{gone}"' in parts[rm], gone


def test_the_version_is_in_the_readme_plugin_section():
    v = load(PLUGIN)["version"]
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("## Install as a Claude Code plugin")
    end = text.find("\n## ", start + 1)
    assert v in text[start:end]


def test_plugin_readme_explains_the_plugin():
    text = (PDIR / "README.md").read_text(encoding="utf-8")
    assert len(text.split()) >= 40
    assert all(f"/{n}" in text for n in ENTRY)
    assert "curl" not in text and "API_KEY" not in text


def test_the_icon_is_declared_and_is_a_flat_svg():
    svg = (PDIR / load(PLUGIN)["icon"]).read_text(encoding="utf-8")
    # the directory refuses nested svg, style, script, foreignObject, animation and event handlers
    assert svg.count("<svg") == 1 and "viewBox" in svg
    assert not re.search(r"<(style|script|foreignObject|animate|set)\b|\son\w+=", svg)


# The directory refuses the plugin when one file in its folder is above 5 MiB ("A file is too large",
# claude.ai/directory/manage, 2026-11-25). The directory only reads the plugin folder, so this covers plugin/.
SIZE_LIMIT = 5 * 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
FORBIDDEN_NAMES = {"claude.md", "claude.local.md", "agents.md"}


def plugin_files(base=PDIR):
    r = subprocess.run(["git", "-C", str(base), "ls-files", "-z", "--", "."], capture_output=True)
    if r.returncode == 0 and r.stdout:
        names = [n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
        return [Path(n) for n in names]
    return [p.relative_to(base) for p in base.rglob("*") if p.is_file() or p.is_symlink()]


def allowlist_errors(base, files, icon):
    errs = []
    for rel in files:
        p = base / rel
        parts = [x.casefold() for x in rel.parts]
        tag = str(rel)
        if p.is_symlink():
            errs.append(f"{tag}: symlink")
            continue
        if rel.as_posix() != icon and rel.suffix.lower() not in ALLOWED_SUFFIXES:
            errs.append(f"{tag}: type not allowed")
        if rel.name.casefold() in FORBIDDEN_NAMES:
            errs.append(f"{tag}: forbidden file name")
        if "node_modules" in parts or ".claude" in parts:
            errs.append(f"{tag}: forbidden folder")
        if ".claude-plugin" in parts and rel.as_posix() != ".claude-plugin/plugin.json":
            errs.append(f"{tag}: only plugin.json may live in .claude-plugin")
        if p.stat().st_size > SIZE_LIMIT:
            errs.append(f"{tag}: above 5 MiB")
        data = p.read_bytes()
        if data.startswith(b"#!"):
            errs.append(f"{tag}: starts with #!")
        if b"\0" in data:
            errs.append(f"{tag}: NUL byte")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            if rel.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
                errs.append(f"{tag}: not UTF-8")
    return errs


def test_the_plugin_folder_passes_the_directory_allow_list():
    files = plugin_files()
    assert files
    assert {f.as_posix() for f in files} >= {".claude-plugin/plugin.json", "icon.svg", "README.md"}
    assert allowlist_errors(PDIR, files, load(PLUGIN)["icon"].removeprefix("./")) == []


def test_the_allow_list_check_rejects_what_the_directory_rejects(tmp_path):
    bad = {"x.py": "print(1)\n", "CLAUDE.md": "x\n", "sub/agents.md": "x\n", "run.md": "#!/bin/sh\n",
           "nul.md": "a\0b", ".claude/skills/a.md": "x\n", "node_modules/a.md": "x\n",
           ".claude-plugin/other.json": "{}", "a.sh": "x"}
    for name, body in bad.items():
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    (tmp_path / "link.md").symlink_to(tmp_path / "run.md")
    (tmp_path / "latin.md").write_bytes(b"a\xe7\xe3o")
    (tmp_path / "ok.md").write_text("fine\n", encoding="utf-8")
    errs = allowlist_errors(tmp_path, plugin_files(tmp_path), "icon.svg")
    flagged = {e.split(":")[0] for e in errs}
    assert flagged == set(bad) | {"link.md", "latin.md"}
