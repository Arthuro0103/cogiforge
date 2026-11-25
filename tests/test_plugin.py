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


def bash_blocks(body):
    return [x.strip() for x in re.findall(r"```bash\n(.*?)```", body, re.S)]


def expected():
    """The exact commands the skills must carry, built from the plugin manifest, never from the skills."""
    m = load(PLUGIN)
    v, repo = m["version"], m["repository"]
    clone = ("git clone -q -c advice.detachedHead=false --depth 1 --branch v" + v + " " + repo + ".git ")
    install = 'cd "$DEST" && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge ' + v + '"'
    guards = (
        "DEST='/absolute/path/to/the/folder' && "
        '{ case "$DEST" in /*) true ;; *) echo "STOP: not an absolute path"; false ;; esac; } && '
        '{ [ "${DEST%/}" != "" ] && [ "${DEST%/}" != "${HOME%/}" ] || { echo "STOP: / and the home folder are never used"; false; }; } && '
        '{ [ ! -e "$DEST" ] || { [ -d "$DEST" ] && [ -r "$DEST" ] && [ -z "$(ls -A "$DEST")" ]; } || '
        '{ echo "STOP: the folder exists and is not empty"; false; }; } && '
        '{ git config user.name >/dev/null && git config user.email >/dev/null || '
        '{ echo "STOP: git has no user.name or user.email"; false; }; } && ')
    return {
        "new": guards + clone + '"$DEST" && rm -rf "$DEST/.git" && ' + install,
        "retry": "cd '/absolute/path/to/the/folder' && " + install.split("&& ", 1)[1],
        "adopt_fresh": "[ ! -e ~/.cogiforge ] && " + clone + "~/.cogiforge && rm -rf ~/.cogiforge/.git",
        "adopt_swap": ("[ ! -e ~/.cogiforge/.git ] && rm -rf ~/.cogiforge.new ~/.cogiforge.old && " + clone +
                       "~/.cogiforge.new && rm -rf ~/.cogiforge.new/.git && mv ~/.cogiforge ~/.cogiforge.old && "
                       "mv ~/.cogiforge.new ~/.cogiforge && rm -rf ~/.cogiforge.old"),
        "adopt_dry": 'python3 ~/.cogiforge/tools/adopt.py "/absolute/path/to/vault"',
        "adopt_apply": 'python3 ~/.cogiforge/tools/adopt.py "/absolute/path/to/vault" --apply --confirm <plan-sha256>',
    }


def test_new_workbench_blocks_are_exactly_the_expected_commands():
    e = expected()
    assert bash_blocks(skill("cf-new-workbench")) == [e["new"], e["retry"]]


def test_adopt_blocks_are_exactly_the_expected_commands():
    e = expected()
    assert bash_blocks(skill("cf-adopt")) == [e["adopt_fresh"], e["adopt_swap"], e["adopt_dry"], e["adopt_apply"]]


def plugin_text_files():
    return [p for p in PDIR.rglob("*") if p.is_file() and p.suffix in {".md", ".json"}]


def test_versions_branches_and_urls_in_the_plugin_are_the_manifest_ones():
    m = load(PLUGIN)
    v, repo = m["version"], m["repository"]
    for p in plugin_text_files():
        text = p.read_text(encoding="utf-8")
        for found in re.findall(r"(?<![\w.])\d+\.\d+\.\d+(?![\w.]*\w)", text):
            assert found == v, (p.name, found)
        for found in re.findall(r"--branch\s+(\S+)", text):
            assert found == "v" + v, (p.name, found)
        for found in re.findall(r"github\.com/[^\s)`'\"<>]*", text):
            url = "https://" + found
            assert url in {repo, repo + ".git"} or url.startswith(repo + "#"), (p.name, found)
    for name in ENTRY:
        body = skill(name)
        assert "--branch v" + v in body and repo + ".git" in body
        assert "${CLAUDE_PLUGIN_ROOT}" not in body and ".in_use" not in body


def test_the_root_readmes_name_only_the_plugin_tag():
    v = load(PLUGIN)["version"]
    for name in ("README.md", "LEIA-ME.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "v" + v in text, name
        for found in re.findall(r"(?<![\w.])v\d+\.\d+\.\d+(?![\w.]*\w)", text):
            assert found == "v" + v, (name, found)


def test_no_verify_only_appears_in_a_line_that_forbids_it():
    for p in plugin_text_files():
        in_code = False
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("```"):
                in_code = not in_code
            if "--no-verify" in line:
                assert not in_code, (p.name, "inside a code block", line)
                assert re.search(r"\b(Never|never|Do not|do not)\b", line), (p.name, line)


def test_adopt_runs_from_the_stable_copy_and_asks_before_replacing():
    body = skill("cf-adopt")
    assert "~/.cogiforge/tools/adopt.py" in body
    assert "--confirm" in body and "--yes" not in body
    assert "NEVER replaces it" in body and "~/.cogiforge/plugin/.claude-plugin/plugin.json" in body


def test_new_workbench_never_overwrites_and_never_skips_the_gate():
    body = skill("cf-new-workbench")
    assert "Never overwrite" in body and "Never use `--no-verify`" in body and "install.sh" in body
    assert "NEVER deletes it" in body
    assert 'rm -rf "$DEST/plugin"' not in body and ".claude-plugin\"" not in bash_blocks(body)[0]


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


TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".svg"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}


def plugin_files(base=PDIR):
    """Tracked files plus untracked-but-not-ignored ones (a new file counts before it is committed)."""
    out = []
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        r = subprocess.run(["git", "-C", str(base), *args, "-z", "--", "."], capture_output=True)
        if r.returncode != 0:
            out = None
            break
        out += [n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
    if out is None:
        return [p.relative_to(base) for p in base.rglob("*") if p.is_file() or p.is_symlink()]
    return [Path(n) for n in dict.fromkeys(out) if (base / n).exists() or (base / n).is_symlink()]


def allowlist_errors(base, files, icon):
    errs = []
    for rel in files:
        p = base / rel
        parts = [x.casefold() for x in rel.parts]
        tag = str(rel)
        suffix = rel.suffix.lower()
        if p.is_symlink():
            errs.append(f"{tag}: symlink")
            continue
        if rel.as_posix() != icon and suffix not in ALLOWED_SUFFIXES:
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
        if data.removeprefix(b"\xef\xbb\xbf").startswith(b"#!"):
            errs.append(f"{tag}: starts with #!")
        if suffix in TEXT_SUFFIXES and b"\0" in data:
            errs.append(f"{tag}: NUL byte")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            if suffix not in IMAGE_SUFFIXES:
                errs.append(f"{tag}: not UTF-8")
    return errs


def test_the_plugin_folder_passes_the_directory_allow_list():
    files = plugin_files()
    assert files
    assert {f.as_posix() for f in files} >= {".claude-plugin/plugin.json", "icon.svg", "README.md"}
    assert allowlist_errors(PDIR, files, load(PLUGIN)["icon"].removeprefix("./")) == []


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082")


def git(base, *args):
    subprocess.run(["git", "-C", str(base), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def test_the_allow_list_check_rejects_what_the_directory_rejects(tmp_path):
    bad = {"x.py": "print(1)\n", "CLAUDE.md": "x\n", "sub/agents.md": "x\n", "run.md": "#!/bin/sh\n",
           "nul.md": "a\0b", ".claude/skills/a.md": "x\n", "node_modules/a.md": "x\n",
           ".claude-plugin/other.json": "{}", "a.sh": "x"}
    for name, body in bad.items():
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    (tmp_path / "bom.md").write_bytes(b"\xef\xbb\xbf#!/bin/sh\n")
    (tmp_path / "link.md").symlink_to(tmp_path / "run.md")
    (tmp_path / "latin.md").write_bytes(b"a\xe7\xe3o")
    (tmp_path / "ok.md").write_text("fine\n", encoding="utf-8")
    (tmp_path / "pixel.png").write_bytes(PNG_1X1)   # a real PNG has NUL bytes and is not UTF-8: it must pass
    errs = allowlist_errors(tmp_path, plugin_files(tmp_path), "icon.svg")   # no git here: the fallback listing
    flagged = {e.split(":")[0] for e in errs}
    assert flagged == set(bad) | {"link.md", "latin.md", "bom.md"}


def test_the_allow_list_check_through_git_lists_tracked_and_untracked_files(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    for name, body in {"x.py": "print(1)\n", "CLAUDE.md": "x\n", "ok.md": "fine\n"}.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    (tmp_path / "pixel.png").write_bytes(PNG_1X1)
    git(tmp_path, "add", "x.py", "CLAUDE.md", "ok.md", "pixel.png", ".gitignore")
    (tmp_path / "run.py").write_text("print(2)\n", encoding="utf-8")        # not tracked: still counts
    (tmp_path / "ignored.py").write_text("print(3)\n", encoding="utf-8")    # ignored: git does not ship it
    files = {f.as_posix() for f in plugin_files(tmp_path)}
    assert files == {"x.py", "CLAUDE.md", "ok.md", "pixel.png", ".gitignore", "run.py"}
    flagged = {e.split(":")[0] for e in allowlist_errors(tmp_path, plugin_files(tmp_path), "icon.svg")}
    assert flagged == {"x.py", "CLAUDE.md", "run.py", ".gitignore"}   # .gitignore has no allowed type either
