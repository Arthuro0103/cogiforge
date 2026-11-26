"""The Claude Code plugin layer: manifest, marketplace, the two entry skills and the directory's allow-list.

The plugin is the `plugin/` folder (the marketplace points at it). It carries only Markdown, JSON and the icon:
the Anthropic directory refuses code from organizations that are not verified, so the skills download this repo
from GitHub at the tag of the plugin's version. The 18 working skills stay in `.claude/skills/` and travel
inside each workbench. These tests read the files, they do not install anything.
"""
import json
import os
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
# The Cogiforge version and commit the plugin installs. The plugin's own version (plugin.json) is separate: the commit
# that holds the skills cannot name its own hash, so the skills pin an EARLIER, tagged commit. To ship a new Cogiforge,
# tag it, then pin its hash here and in both skills and raise the plugin version, in one commit.
PIN_VERSION = "0.1.2"
PIN_SHA = "74177d483c444ee628114f56770fe5d111e97b29"
REPO_GIT = "https://github.com/Arthuro0103/cogiforge.git"


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


FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])(\s+)")


def code_in(body):
    """Every piece of code in a Markdown text, in order: (kind, raw_opening_line, text, line numbers).

    kind is "fence" for a ``` or ~~~ block (any indentation, any info text, so "```bash " and "~~~bash" count)
    and "indented" for a block indented by 4 spaces or a tab (even inside a list). A fence that never closes is reported too."""
    lines = body.split("\n")
    out, i, prev_blank = [], 0, True
    while i < len(lines):
        line = lines[i]
        m = FENCE.match(line)
        if m and not (m.group(2)[0] == "`" and "`" in m.group(3)):
            ch, n = m.group(2)[0], len(m.group(2))
            j = i + 1
            while j < len(lines) and not re.match(r"^\s*" + re.escape(ch) + "{" + str(n) + r",}\s*$", lines[j]):
                j += 1
            closed = j < len(lines)
            out.append(("fence" if closed else "open-fence", line, "\n".join(lines[i + 1:j]), range(i, min(j, len(lines) - 1) + 1)))
            i, prev_blank = j + 1, False
            continue
        if line.strip() == "":
            prev_blank = True
            i += 1
            continue
        li = LIST_ITEM.match(line)
        tab = line.startswith("\t") or line.startswith("    ")
        # stricter than CommonMark on purpose: 4 spaces or a tab after a blank line is code even inside a list
        # (a model may run it), and no legitimate line of these skills is indented that much
        if tab and prev_blank and not li:
            j = i
            while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith(("    ", "\t"))):
                j += 1
            out.append(("indented", line, "\n".join(x.strip() for x in lines[i:j]).strip(), range(i, j)))
            i = j
            prev_blank = True
            continue
        prev_blank = False
        i += 1
    return out


def bash_blocks(body):
    """The text of the fenced blocks, and nothing is allowed to be anything but exactly a ```bash fence."""
    return [x[2].strip() for x in code_in(body) if x[0] == "fence"]


def prose_lines(body):
    """(text, in_code) for each line, so a rule can look only at the prose."""
    lines = body.split("\n")
    code = set()
    for kind, _, _, rng in code_in(body):
        code.update(rng)
    return [(l, k in code) for k, l in enumerate(lines)]


def expected():
    """The exact commands the skills must carry, built from the pinned version and hash, never from the skills."""
    def fetch(d):
        return (f"git init -q {d} && git -C {d} fetch -q --depth 1 {REPO_GIT} {PIN_SHA} && "
                f"git -C {d} -c advice.detachedHead=false checkout -q FETCH_HEAD && "
                f'{{ [ "$(git -C {d} rev-parse HEAD)" = "{PIN_SHA}" ] || '
                '{ echo "STOP: the download is not the pinned commit"; false; }; } && ')
    v = PIN_VERSION
    commit = 'cd "$DEST" && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge ' + v + '"'
    env = "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR && "
    dest = "DEST='/absolute/path/to/the/folder' && "
    absolute = '{ case "$DEST" in /*) true ;; *) echo "STOP: not an absolute path"; false ;; esac; } && '
    guards = (
        env + dest + absolute +
        '{ case "$DEST/" in */./*|*/../*) echo "STOP: the path has . or .. in it"; false ;; *) true ;; esac; } && '
        '{ [ "${DEST%/}" != "" ] && [ "${DEST%/}" != "${HOME%/}" ] || { echo "STOP: / and the home folder are never used"; false; }; } && '
        '{ [ ! -e "$DEST" ] || { [ -d "$DEST" ] && [ -r "$DEST" ] && [ -x "$DEST" ] && [ -z "$(ls -A "$DEST")" ]; } || '
        '{ echo "STOP: the folder exists and is not empty"; false; }; } && '
        '{ git -C / config user.name >/dev/null && git -C / config user.email >/dev/null || '
        '{ echo "STOP: git has no global user.name or user.email"; false; }; } && ')
    home = '{ [ -n "$HOME" ] && [ "$HOME" != "/" ] || { echo "STOP: HOME is not set"; false; }; } && '
    return {
        "new": guards + fetch('"$DEST"') + 'rm -rf "$DEST/.git" && ' + commit,
        "retry": (env + dest + absolute +
                  '{ [ -f "$DEST/install.sh" ] && [ -f "$DEST/core/memory.py" ] || '
                  '{ echo "STOP: this folder is not a Cogiforge workbench"; false; }; } && ' + commit),
        "adopt_fresh": (home + '{ [ ! -e ~/.cogiforge ] && [ ! -e ~/.cogiforge.new ] || '
                        '{ echo "STOP: ~/.cogiforge or ~/.cogiforge.new already exists"; false; }; } && ' + fetch("~/.cogiforge.new") +
                        f"rm -rf ~/.cogiforge.new/.git && printf '%s\\n' {PIN_SHA} > ~/.cogiforge.new/.cogiforge-commit && "
                        "mv ~/.cogiforge.new ~/.cogiforge"),
        "adopt_swap": (home + '{ [ -f ~/.cogiforge/tools/adopt.py ] && [ ! -e ~/.cogiforge/.git ] || '
                       '{ echo "STOP: ~/.cogiforge is missing, incomplete, or a git clone"; false; }; } && '
                       '{ [ ! -e ~/.cogiforge.new ] && [ ! -e ~/.cogiforge.old ] || '
                       '{ echo "STOP: ~/.cogiforge.new or ~/.cogiforge.old is left from an earlier try"; false; }; } && ' + fetch("~/.cogiforge.new") +
                       f"rm -rf ~/.cogiforge.new/.git && printf '%s\\n' {PIN_SHA} > ~/.cogiforge.new/.cogiforge-commit && "
                       "mv ~/.cogiforge ~/.cogiforge.old && "
                       "mv ~/.cogiforge.new ~/.cogiforge && rm -rf ~/.cogiforge.old"),
        "adopt_dry": "python3 ~/.cogiforge/tools/adopt.py '/absolute/path/to/vault'",
        "adopt_apply": "python3 ~/.cogiforge/tools/adopt.py '/absolute/path/to/vault' --apply --confirm <plan-sha256>",
    }


def code_errors(body, want):
    """Every piece of code in a skill must be exactly one of the expected ```bash blocks, nothing more."""
    errs = []
    got = []
    for kind, opening, text, _ in code_in(body):
        if kind != "fence" or opening != "```bash":
            errs.append(f"{kind} code block ({opening.strip()[:20]!r}): only exact ```bash fences are allowed")
        if kind == "fence":
            got.append(text.strip())
    if got != want:
        errs.append(f"blocks differ from the expected ones: got {len(got)}, want {len(want)}")
    return errs


def test_new_workbench_blocks_are_exactly_the_expected_commands():
    e = expected()
    assert code_errors(skill("cf-new-workbench"), [e["new"], e["retry"]]) == []


def test_adopt_blocks_are_exactly_the_expected_commands():
    e = expected()
    want = [e["adopt_fresh"], e["adopt_swap"], e["adopt_dry"], e["adopt_apply"]]
    assert code_errors(skill("cf-adopt"), want) == []


IMAGE_MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",), ".gif": (b"GIF87a", b"GIF89a"), ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",), ".ico": (b"\x00\x00\x01\x00",),
}


def is_real_image(suffix, data):
    if suffix == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return any(data.startswith(m) for m in IMAGE_MAGIC.get(suffix, ()))


# The one exact set of files the plugin folder may hold. Anything else (hooks, an MCP config, commands, notes) changes
# what the plugin can do, so it is a decision, not a side effect.
PLUGIN_FILES = {".claude-plugin/plugin.json", "README.md", "icon.svg", "skills/cf-new-workbench/SKILL.md",
                "skills/cf-adopt/SKILL.md"}

# Sentences that protect the person. Each one has to stay in the skill that owns it, word for word.
SAFETY = {
    "cf-new-workbench": [
        "**Never overwrite.**", "Do not delete anything to make room.", "Never use `--no-verify`.",
        "Never split it into lines or into separate calls.", "this skill NEVER deletes it",
        "This retry command is only for the folder the main command just downloaded",
        "If git says `nothing to commit`, the first commit already happened",
        "never guess which step failed", "Or the person deletes the folder themselves and the skill runs again.",
        "If the folder exists and is not empty, stop and say so.",
        "STOP: the download is not the pinned commit", "never run `install.sh` or anything else from that folder",
        "The person deletes the folder themselves and tries again; this skill never deletes it.",
        "the command checks that hash before it runs anything from the download",
    ],
    "cf-adopt": [
        "Never replace it without a yes.", "this skill NEVER replaces it",
        "**Dry run first, always.**", "Do not run `--apply` before the user has seen the plan.",
        "Only after a clear \"yes\"", "(never a sha from an older run)", "A \"maybe\" or silence is a no.",
        "If the second `mv` fails, run `mv ~/.cogiforge.old ~/.cogiforge` to go back",
        "a swap stopped in the middle: run `mv ~/.cogiforge.old ~/.cogiforge` to go back",
        "treat it as another version",
        "This skill never deletes `~/.cogiforge.old` or `~/.cogiforge.new` by itself",
        "Never run `git init` or `--apply` before the plan was read and confirmed, and never use `--no-verify`.",
        "ask the person to rename the folder or give another path",
        "Never run anything from a download that failed the check.", "run nothing from a download that failed",
        "checks that hash before it runs anything from the download",
    ],
}


def safety_errors(name, body):
    prose = "\n".join(l for l, in_code in prose_lines(body) if not in_code)
    return [f"{name}: missing {s!r}" for s in SAFETY[name] if s not in prose]


def test_the_safety_sentences_are_still_in_each_skill():
    for name in ENTRY:
        assert safety_errors(name, skill(name)) == []


def plugin_text_files(base=PDIR):
    """EVERY file of the plugin folder that is text (images are skipped: they have no words to read)."""
    out = []
    for rel in plugin_files(base):
        if rel.suffix.lower() in IMAGE_SUFFIXES:
            continue
        out.append((rel, (base / rel).read_bytes().decode("utf-8", "replace")))
    return out


VERSION_RE = re.compile(r"\bv?\d+(\.\d+){1,3}(-[0-9A-Za-z.]+)?\b")
TRIPLE_RE = re.compile(r"\d+\.\d+\.\d+")
URL_RE = re.compile(r"https?://[^\s)`'\"<>\]]+|git@[^\s)`'\"<>]+|[A-Za-z0-9.-]*github[A-Za-z0-9.-]*\.com[^\s)`'\"<>\]]*")
SVG_NS = "http://www.w3.org/2000/svg"
NO_VERIFY_RE = re.compile(r"--no-verify|\bcommit\b[^\n]*?\s-[A-Za-z]*n[A-Za-z]*(?=\s|$)")


def reference_errors(files, version, repo, also=None):
    """Versions, URLs and hook-skipping flags in every text file. `files` is a list of (path, text).
    `also` maps a path (as text) to extra versions that file may name (the plugin's own version, in one place)."""
    errs = []
    for rel, text in files:
        tag = Path(rel).as_posix()   # / on every OS, so names match on Windows too
        extra = (also or {}).get(tag, set())
        for m in VERSION_RE.finditer(text):
            found = m.group(0)
            if found.startswith("v"):
                if found != "v" + version and found[1:] not in extra:
                    errs.append(f"{tag}: version {found}")
            elif found.count(".") >= 2 and found != version and found not in extra:
                errs.append(f"{tag}: version {found}")
        for found in TRIPLE_RE.findall(text):
            if found != version and found not in extra:
                errs.append(f"{tag}: version {found}")
        for found in URL_RE.findall(text):
            found = found.rstrip(".,;:")
            if found == SVG_NS and str(rel).endswith(".svg"):
                continue
            if not (found in {repo, repo + ".git"} or found.startswith(repo + "#")):
                errs.append(f"{tag}: url {found}")
        in_code = {k for k, (_, c) in enumerate(prose_lines(text)) if c}
        for k, line in enumerate(text.split("\n")):
            if not NO_VERIFY_RE.search(line):
                continue
            if k in in_code or not str(rel).endswith(".md"):
                errs.append(f"{tag}: hook-skipping flag in code or in a non-prose file: {line.strip()[:60]}")
                continue
            plain = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line.replace("**", ""))
            for sentence in re.split(r"(?<=[.!?])\s+", plain):
                m = NO_VERIFY_RE.search(sentence)
                if m and not (re.match(r"(Never|Do not) (use|run|pass|add|skip|bypass)\b", sentence)
                              and not re.search(r"[:;]", sentence[:m.start()])):
                    errs.append(f"{tag}: the flag is not in a sentence that forbids it: {sentence[:60]}")
    return errs


def semver(s):
    return tuple(int(x) for x in s.split("."))


def test_versions_urls_and_hook_skipping_in_every_plugin_file():
    m = load(PLUGIN)
    repo = m["repository"]
    # plugin.json carries the plugin's own version; plugin/README.md may cite it in the one sentence about pinning
    also = {".claude-plugin/plugin.json": {m["version"]}, "README.md": {m["version"]}}
    assert reference_errors(plugin_text_files(), PIN_VERSION, repo, also) == []
    assert m["homepage"] == repo
    assert semver(m["version"]) >= semver(PIN_VERSION)
    for name in ENTRY:
        body = skill(name)
        assert "${CLAUDE_PLUGIN_ROOT}" not in body and ".in_use" not in body
        # the download is by hash only: no git clone of the repo, no branch or tag
        assert not re.search(r"git clone\s+(-|\S*://)", body) and "--branch" not in body, name


def test_the_pin_is_one_hash_everywhere_and_checked_before_anything_runs():
    assert re.fullmatch(r"[0-9a-f]{40}", PIN_SHA)
    for rel, text in plugin_text_files():
        for found in re.findall(r"(?<![0-9A-Za-z])[0-9a-f]{40}(?![0-9A-Za-z])", text):
            assert found == PIN_SHA, (str(rel), found)
        for short in re.findall(r"(?<![0-9A-Za-z])[0-9a-f]{7,39}(?![0-9A-Za-z])", text):
            if re.search(r"[a-f]", short) and re.search(r"\d", short):
                assert PIN_SHA.startswith(short), (str(rel), short)
    for name in ENTRY:
        body = skill(name)
        blocks = [b for b in bash_blocks(body) if "fetch" in b]
        assert blocks and all(b.count(PIN_SHA) >= 2 for b in blocks), name
        assert all(f'[ "$(git -C ' in b and f'rev-parse HEAD)" = "{PIN_SHA}" ]' in b for b in blocks), name
        for b in blocks:
            # the check comes after the checkout and before anything is removed, moved or run
            check = b.index("rev-parse HEAD")
            assert b.index("checkout -q FETCH_HEAD") < check
            for later in ("rm -rf", "mv ", "install.sh", "printf"):
                assert later not in b[:check], (name, later)


def test_the_root_readmes_name_only_the_pinned_tag():
    for name in ("README.md", "LEIA-ME.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "v" + PIN_VERSION in text, name
        for found in re.findall(r"(?<![\w.])v\d+\.\d+\.\d+(?![\w.]*\w)", text):
            assert found == "v" + PIN_VERSION, (name, found)


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
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("## Install as a Claude Code plugin")
    end = text.find("\n## ", start + 1)
    assert "Claude Code plugin" in text[start:end]
    assert PIN_VERSION in (ROOT / "README.md").read_text(encoding="utf-8")


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
        tag = Path(rel).as_posix()   # / on every OS, so names match on Windows too
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
        if suffix in IMAGE_SUFFIXES and not is_real_image(suffix, data):
            errs.append(f"{tag}: the bytes are not a {suffix} image")
    return errs


def test_the_plugin_folder_passes_the_directory_allow_list():
    files = plugin_files()
    assert files
    assert {f.as_posix() for f in files} >= {".claude-plugin/plugin.json", "icon.svg", "README.md"}
    assert allowlist_errors(PDIR, files, load(PLUGIN)["icon"].removeprefix("./")) == []


def test_the_plugin_folder_holds_exactly_the_five_expected_files():
    got = {f.as_posix() for f in plugin_files()}
    assert got == PLUGIN_FILES, (sorted(got - PLUGIN_FILES), sorted(PLUGIN_FILES - got))


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


def test_an_image_name_with_other_bytes_is_rejected(tmp_path):
    good = {"a.gif": b"GIF89a" + bytes(8), "b.gif": b"GIF87a" + bytes(8), "c.jpg": b"\xff\xd8\xff\xe0" + bytes(8),
            "d.jpeg": b"\xff\xd8\xff\xdb" + bytes(8), "e.webp": b"RIFF\x04\0\0\0WEBPVP8 ", "f.ico": b"\x00\x00\x01\x00" + bytes(8),
            "g.png": PNG_1X1}
    bad = {"macho.png": b"\xcf\xfa\xed\xfe\x07\x00\x00\x01" + bytes(64), "text.png": b"not an image",
           "wrong.gif": PNG_1X1, "riff.webp": b"RIFF\x04\0\0\0WAVEfmt "}
    for name, data in {**good, **bad}.items():
        (tmp_path / name).write_bytes(data)
    flagged = {e.split(":")[0] for e in allowlist_errors(tmp_path, plugin_files(tmp_path), "icon.svg")}
    assert flagged == set(bad)


def test_code_in_finds_every_kind_of_block():
    body = ("a\n\n```bash\nx\n```\n\n```bash \ny\n```\n\n~~~bash\nz\n~~~\n\n```sh\nw\n```\n\n    indented\n\n"
            "- item\n\n  continues here\n\n```\nopen but never closed\n")
    kinds = [(k, o.strip()) for k, o, _, _ in code_in(body)]
    assert kinds == [("fence", "```bash"), ("fence", "```bash"), ("fence", "~~~bash"), ("fence", "```sh"),
                     ("indented", "indented"), ("open-fence", "```")]
    assert code_in("- item\n\n   text in a list at 3 spaces\n\n1. one\n   more\n") == []
    assert [k for k, *_ in code_in("para\n\n\tcode with tab\n")] == ["indented"]
    assert code_errors("```bash\nx\n```\n", ["x"]) == [] and code_errors("```bash \nx\n```\n", ["x"]) != []


def test_reference_errors_catch_what_the_old_check_missed():
    repo = "https://github.com/Arthuro0103/cogiforge"

    def errs(text, name="x.md"):
        return reference_errors([(Path(name), text)], "0.1.1", repo)
    assert reference_errors([(Path("p.md"), "plugin 0.1.2")], "0.1.1", repo, {"p.md": {"0.1.2"}}) == []
    assert reference_errors([(Path("p.md"), "plugin 0.1.2")], "0.1.1", repo)
    assert errs("tag v0.1.1 and 0.1.1 and " + repo + ".git and " + repo + "#readme\n") == []
    for bad in ("tag v0.1.1-rc1", "tag v0.2", "tag 0.1.0", "see 9.9.9", "ssh git@github.com:Other/x.git",
                "https://gitlab.com/o/x.git", "https://raw.githubusercontent.com/O/x/main/i.sh",
                "https://github.com/Other/cogiforge", "`git commit --no-verify`", "Never mind: run `git commit --no-verify`",
                "x git commit -n -qm y"):
        assert errs(bad + "\n"), bad
    assert errs("Never use `--no-verify`.\n") == [] and errs("- Do not run `git commit -n`.\n") == []
    assert errs("```bash\ngit commit --no-verify\n```\n") and errs("    git commit --no-verify\n")
    assert errs("Never use `--no-verify`.\n", "NOTES.txt")
    assert errs('<svg xmlns="http://www.w3.org/2000/svg"/>\n', "icon.svg") == []


@pytest.mark.skipif(os.environ.get("COGIFORGE_CHECK_TAG") != "1",
                    reason="set COGIFORGE_CHECK_TAG=1 (needs network) to check the pinned tag and commit on GitHub")
def test_the_release_tag_is_the_pinned_commit_on_github(tmp_path):
    r = subprocess.run(["git", "ls-remote", "--tags", REPO_GIT, f"refs/tags/v{PIN_VERSION}", f"refs/tags/v{PIN_VERSION}^{{}}"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == [PIN_SHA, f"refs/tags/v{PIN_VERSION}"], r.stdout   # a plain tag: no ^{} line
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "fetch", "-q", "--depth", "1", REPO_GIT, PIN_SHA], check=True, timeout=120)
    got = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "FETCH_HEAD"], capture_output=True, text=True, check=True)
    assert got.stdout.strip() == PIN_SHA
