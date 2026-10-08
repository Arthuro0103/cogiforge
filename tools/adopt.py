#!/usr/bin/env python3
"""adopt.py: applies the cogiforge to an Obsidian vault you ALREADY have, in place, copying nothing. Stdlib only.

    python3 tools/adopt.py VAULT [--apply [--yes]] [--json]
    python3 tools/adopt.py --selftest

VAULT is the root of your vault (the folder that holds your notes and, ideally, `.git`). The default is a DRY
RUN: it prints the plan and writes nothing. The plan has four parts:
  1. areas        the top-level folders that hold notes, as a proposed `areas.txt` (`folder: area` lines).
                  Hidden folders, `.obsidian`, `.git`, `.trash`, attachment folders and deposits (`inbox`,
                  `tasks`, templates) are not areas.
  2. install      what `--apply` would create: `.githooks/pre-commit` (calls the cogiforge gate, ring and
                  leak scanner from this checkout; the full hook text is printed), `areas.txt`,
                  `.cogiforge/baseline.json`, and two entries of the LOCAL git config: `cogiforge.home` (where
                  this checkout lives; the hook reads it from `.git/config`, never from a file in the working tree, so a
                  vault received from outside cannot redirect it) and `core.hooksPath .githooks`. A file that already
                  exists is NEVER overwritten: it becomes a CONFLICT item in the report.
  3. debt         measured today: orphan notes, dead wikilinks, notes in an area folder without `area:`
                  (and notes whose frontmatter the gate cannot parse). It is saved as the baseline.
  4. the warning  the hook only judges the notes IN THE COMMIT, so the old debt blocks nobody.

`core.hooksPath` is only activated when `.githooks/pre-commit` does not exist or is byte for byte the generated one;
a different hook (someone else's code) is a BLOCKING conflict: the plan shows its first lines, `--apply` writes
nothing, and you have to read that hook and decide. The hook refuses to run (blocks the commit) if `cogiforge.home`
is not an absolute path to a folder holding core/ring.py, core/gate.py and core/leak.py.

THREAT MODEL (6 lines)
  1. DEFENDS: a vault received from a third party (zip, copy, sync) whose `.git`, `.githooks` or notes are hostile.
  2. `.git/config` is not parsed by adopt: git itself lists a private copy (`git config --file COPY --list -z --no-includes`,
     clean environment, which runs nothing), and an ALLOWLIST judges the pairs git returned (core.repositoryformatversion,
     filemode, bare, logallrefupdates, ignorecase, precomposeunicode, symlinks; remote.*.url/fetch; branch.*.remote/merge;
     user.name/email) plus the two keys adopt writes. Any other key, an include, or a file git cannot parse blocks (rc 1,
     entry cited, nothing written, no git run inside the vault). Size, NUL and UTF-8 are only extra belt checks.
  3. `.git` is judged as a whole, default-deny: only the names of a plain repository (HEAD, config, description, index, packed-refs,
     hooks of `*.sample`, info/exclude, objects, refs, logs, ...). `commondir`, `config.worktree`, `info/attributes`, alternates,
     modules, worktrees, shallow, rebase/sequencer state, a hook of yours or any symlink block: git reads them too.
     It also refuses symlinks in any component of a path it would write, `.git` that is a symlink or a file, a `.githooks` that
     holds anything but the generated `pre-commit`, a different `pre-commit`, and a `cogiforge.home` that is not this checkout.
  4. The generated hook accepts `cogiforge.home` only as a canonical absolute path (no `.`/`..`, no symlink) with the three
     scripts inside, and passes note names after `--`. Text from the vault never reaches the terminal raw: every output goes through one
     function that shows control, format (bidi, zero-width), separator and surrogate characters as `\\xNN`/`\\uNNNN`, and the
     hook filters what it quotes with `tr`. `--json` is ASCII-only.
  5. DOES NOT DEFEND: you pointing `cogiforge.home` at a clone you chose yourself (it checks the three scripts exist, not who
     wrote them), nor a hook you read and approved, nor a hostile global git config or `PATH` of your own account.
  6. When the allowlist blocks something you consider fine, the fix is to edit `.git/config` yourself; adopt never loosens it.

`--apply` runs only after the plan was printed, and needs `--yes` or an interactive "yes". It writes only what the
plan listed and never touches an existing note. It never runs `git init`: a vault that is not a git repository
(or sits inside a bigger one) is reported as pending and `--apply` writes nothing (rc 1).

Skipped and listed, never counted as "no problem": iCloud placeholders that are not downloaded ("dataless":
st_blocks 0 with st_size > 0), unreadable or non-UTF-8 notes, and symlinks. A vault with no note says
"nothing to adopt", never OK. The area check of `core/gate.py` only applies under `notes/`; elsewhere the area
numbers are information.

rc: 0 plan ok (or applied) and nothing pending · 1 something is pending (not a git repo, conflict, skipped
file, nothing to adopt) · 2 usage, or `--apply` without confirmation · 3 vault unreadable
"""
import argparse
import collections
import contextlib
import datetime
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import gate  # noqa: E402
import ring  # noqa: E402

NOT_AREAS = {"inbox", "tasks", "templates", "template", "_templates", "attachments", "_attachments", "assets",
             "attach", "files", "images", "img", "media", "resources", "_resources", "excalidraw"}
HOOK = ".githooks/pre-commit"
BASELINE = ".cogiforge/baseline.json"
AREAS = "areas.txt"
LIST_CAP = 50
HOOK_PEEK = 15

HOOK_TEXT = """#!/bin/sh
# pre-commit installed by cogiforge tools/adopt.py. It only judges what THIS commit carries.
# The cogiforge checkout is read from the LOCAL git config (cogiforge.home), never from a file of the working tree.
# Output that quotes names from the commit goes through `tr`: no control character reaches the terminal.
# Deliberate bypass: git commit --no-verify

root=$(git rev-parse --show-toplevel) || exit 1
cd "$root" || exit 1
home=$(git config --local --get cogiforge.home)
block() { echo "  COMMIT BLOCKED: $1" >&2; echo "  Fix: git config --local cogiforge.home <absolute path of your cogiforge checkout>" >&2; exit 1; }
case "$home" in
    /*|[A-Za-z]:/*) ;;  # POSIX, or a Windows drive path written with `/` (D:/a/x)
    *) block "cogiforge.home is not set to an absolute path." ;;
esac
case "$home/" in
    */../*|*/./*|*//*) block "cogiforge.home has a . or .. or empty component." ;;
esac
[ -d "$home" ] || block "cogiforge.home is not a folder."
canon=$(cd "$home" 2>/dev/null && pwd -P)
# Git for Windows prints /d/a/x for D:/a/x; cygpath -m gives back the drive form that cogiforge.home uses
if command -v cygpath >/dev/null 2>&1; then canon=$(cygpath -m "$canon" 2>/dev/null); fi
[ "$canon" = "$home" ] || block "cogiforge.home is not a canonical path (a symlink in it?)."
for f in core/gate.py core/ring.py core/leak.py; do
    [ -f "$home/$f" ] || block "cogiforge.home does not contain $f."
done
out=$(mktemp) || exit 1
trap 'rm -f "$out"' EXIT
blocked=0

if git diff --cached --name-only --diff-filter=ACMR -z | grep -qz '\\.md$'; then
    if ! python3 "$home/core/ring.py" --vault . --gate --stage >"$out" 2>&1; then
        echo "  COMMIT BLOCKED: a note in this commit has no link"
        LC_ALL=C tr -c '[:print:]\\n' '?' < "$out" | sed 's/^/     /' | head -20
        blocked=1
    fi
    if ! git diff --cached --name-only --diff-filter=ACMR -z -- '*.md' | xargs -0 python3 "$home/core/gate.py" --vault . -- >"$out" 2>&1; then
        echo "  COMMIT BLOCKED: a note in this commit fails the gate"
        LC_ALL=C tr -c '[:print:]\\n' '?' < "$out" | sed 's/^/     /' | head -20
        blocked=1
    fi
fi

if ! python3 "$home/core/leak.py" --staged >"$out" 2>&1; then
    echo "  COMMIT BLOCKED: personal data in what is going into the commit"
    LC_ALL=C tr -c '[:print:]\\n' '?' < "$out" | sed 's/^/     /' | head -20
    blocked=1
fi

[ "$blocked" -eq 0 ] || { echo "  Deliberate bypass: git commit --no-verify"; exit 1; }
exit 0
"""


def is_dataless(path):
    """iCloud placeholder that is not downloaded: no blocks on disk, but a size."""
    st = os.lstat(path)
    # Windows has no st_blocks (and no iCloud placeholders): there it is never dataless.
    return st.st_size > 0 and getattr(st, "st_blocks", 1) == 0


def git_state(vault):
    """('ok'|'no-git'|'nested'|'unsafe'|'no-binary', detail). Runs NO git: a vault from outside is not trusted,
    and git may execute commands named in the config of the repo it is pointed at."""
    vault = Path(vault).resolve()
    g = vault / ".git"
    if g.is_symlink():
        return "unsafe", ".git is a symlink"
    if g.is_file():
        return "unsafe", ".git is a file (worktree or submodule): adopt needs a plain repository"
    if g.is_dir():
        return ("ok", None) if shutil.which("git") else ("no-binary", None)
    for parent in vault.parents:
        if (parent / ".git").exists():
            return "nested", parent.name
    return "no-git", None


# ALLOWLIST of what `git init` / `git clone` write into a repo's local config, plus the two keys adopt writes.
# The config is NOT parsed here: git itself lists it (`git config --file COPY --list -z --no-includes`, which executes
# nothing, proved by tests with fsmonitor, alias, filter and diff.external decoys), so what git understands is what is
# judged. The allowlist applies to the (key, value) pairs git returned, key as git normalizes it (section and name in
# lowercase, subsection kept), value exact. Any other key (include.path and includeIf too) blocks.
BOOLV = r"true|false"
_PATH = r"[A-Za-z0-9_./+~ -]*"
_NAME = r"(?:(?!\.\.)[A-Za-z0-9_./-])+"
ALLOWED_KEYS = [
    (r"core\.repositoryformatversion", r"0"), (r"core\.filemode", BOOLV), (r"core\.bare", r"false"),
    (r"core\.logallrefupdates", r"true"), (r"core\.ignorecase", BOOLV), (r"core\.precomposeunicode", BOOLV),
    (r"core\.symlinks", BOOLV), (r"core\.hookspath", r"\.githooks"),
    (r"remote\." + _NAME + r"\.url", r"(?:(?:https?|ssh|git)://(?:[A-Za-z0-9_][A-Za-z0-9_.~%+-]*@)?[A-Za-z0-9][A-Za-z0-9_.-]*"
                                      r"(?::[0-9]{1,5})?(?:/[A-Za-z0-9_.~%+@:/-]*)?"
                                      r"|(?:[A-Za-z0-9_][A-Za-z0-9_.-]*@)?[A-Za-z0-9][A-Za-z0-9_.-]*:(?!//)[A-Za-z0-9_.~/+-]*"
                                      r"|/" + _PATH + r"|\.{1,2}/" + _PATH + ")"),
    (r"remote\." + _NAME + r"\.fetch", r"\+?[A-Za-z0-9_./*-]+:[A-Za-z0-9_./*-]+"),
    (r"branch\." + _NAME + r"\.remote", r"\.|[A-Za-z0-9_.-]+"), (r"branch\." + _NAME + r"\.merge", r"refs/[A-Za-z0-9_./-]+"),
    (r"user\.name", r"[\w.@+' ,()-]{1,100}"), (r"user\.email", r"[\w.@+'-]{1,100}"),
    (r"cogiforge\.home", None),  # compared with the checkout path, not by pattern
]
ROOT_SAFE = re.compile(r"^(?:[A-Za-z]:)?/[A-Za-z0-9_./+@~ -]+$")  # a path adopt can write to the config and read back exactly
MAX_CONFIG_BYTES = 64 * 1024
CLEAN_GIT_ENV_KEEP = ("PATH",)


def clean_git_env(home):
    """An environment that gives git nothing to read or run beyond the file it is pointed at."""
    env = {k: os.environ[k] for k in CLEAN_GIT_ENV_KEEP if k in os.environ}
    if sys.platform == "win32":  # git for Windows cannot start without these two
        env.update({k: os.environ[k] for k in ("SYSTEMROOT", "USERPROFILE") if k in os.environ})
        env["USERPROFILE"] = str(home)
    env.update({"HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0"})
    return env


def git_list(path, home):
    """[(key, value|None)] exactly as git lists the file at `path`, or raises ValueError(why)."""
    r = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "config", "--file", str(path),
                        "--list", "-z", "--no-includes"], capture_output=True, cwd=str(home), env=clean_git_env(home))
    if r.returncode != 0:
        raise ValueError("git could not parse it: " + r.stderr.decode("utf-8", "replace").strip().splitlines()[0][:120]
                         if r.stderr.strip() else "git could not parse it")
    out = []
    for rec in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if rec:
            key, nl, val = rec.partition("\n")
            out.append((key, val if nl else None))
    return out


def judge(pairs):
    """(entries, violations) of git's own (key, value) list against the allowlist."""
    entries, bad = [], []
    for key, val in pairs:
        why = None
        for kre, vre in ALLOWED_KEYS:
            if re.fullmatch(kre, key):
                if val is None:
                    why = "key without a value"
                elif key == "cogiforge.home":
                    why = None if val == ROOT.as_posix() else "cogiforge.home is not this checkout"
                elif not re.fullmatch(vre, val):
                    why = "value outside the accepted pattern"
                break
        else:
            why = "key not in the allowlist of what git init/clone writes"
        if why:
            bad.append((key, val, why))
        else:
            entries.append((key, val))
    return entries, bad


def validate_git_config(data):
    """(entries, violations) for a config given as BYTES. Belt checks on the bytes (not the source of truth), then git
    lists a private COPY of exactly these bytes and the allowlist judges what git returned."""
    if len(data) > MAX_CONFIG_BYTES:
        return [], [("(file)", None, f"larger than {MAX_CONFIG_BYTES} bytes")]
    if b"\x00" in data:
        return [], [("(file)", None, "NUL byte")]
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return [], [("(file)", None, "not valid UTF-8")]
    if not shutil.which("git"):
        return [], [("(git)", None, "git is not installed, so the config cannot be parsed")]
    with tempfile.TemporaryDirectory(prefix="adopt-cfg-") as td:
        copy = Path(td) / "config"
        copy.write_bytes(data)
        try:
            pairs = git_list(copy, td)
        except ValueError as e:
            return [], [("(file)", None, str(e))]
    return judge(pairs)


def read_repo_config(vault):
    """(entries, violations) of the local config of the repo."""
    cfg = Path(vault) / ".git" / "config"
    if cfg.is_symlink():
        return [], [(".git/config", None, "is a symlink")]
    if not cfg.exists():
        return [], []
    if not cfg.is_file():
        return [], [(".git/config", None, "is not a regular file")]
    try:
        return validate_git_config(cfg.read_bytes())
    except OSError as e:
        return [], [(".git/config", None, f"unreadable ({type(e).__name__})")]


def write_local_config(vault, key, value):
    """Writes one key to the vault's own .git/config through git, with no repo discovery in the vault and no env."""
    with tempfile.TemporaryDirectory(prefix="adopt-w-") as td:
        subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "config", "--file",
                        str(Path(os.path.abspath(vault)) / ".git" / "config"), key, value],
                       capture_output=True, cwd=td, env=clean_git_env(td), check=True)


def lookup(entries, key):
    vals = [v for k, v in entries if k == key]
    return vals[-1] if vals else ""


# Text that did not come from this file (names, config lines, hook lines, git's own messages) never reaches the terminal
# raw: every control, format, separator and surrogate character is shown as a visible \xNN / \uNNNN escape.
def safe(s):
    out = []
    for c in str(s):
        o = ord(c)
        if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn") or o == 0x7F:
            out.append(f"\\x{o:02x}" if o < 0x100 else (f"\\u{o:04x}" if o < 0x10000 else f"\\U{o:08x}"))
        else:
            out.append(c)
    return "".join(out)


shown_text = safe  # the one function; the old name stays so call sites read the same


def emit(text="", file=None):
    """The ONLY way adopt writes text to a stream: line by line through safe()."""
    print("\n".join(safe(line) for line in str(text).split("\n")), file=file or sys.stdout)


# A plain repository, as `git init` and ordinary use leave it. Git consults MORE than `.git/config` (commondir points
# its config, hooks and objects elsewhere; config.worktree, info/attributes, alternates, modules, worktrees, shallow and the
# rebase/sequencer state can all change what runs or what is read), so the layout is default-deny too: a name that is not
# in these sets, a symlink, or a file of the wrong kind blocks.
GIT_TOP_FILES = {"HEAD", "config", "description", "index", "packed-refs", "COMMIT_EDITMSG", "ORIG_HEAD", "FETCH_HEAD"}
GIT_TOP_DIRS = {"hooks", "info", "objects", "refs", "logs"}
GIT_INFO_OK = {"exclude", "refs"}  # refs: the dumb-http index git gc writes; data, no execution
GIT_OBJECTS_INFO_OK = {"packs", "commit-graph", "commit-graphs"}
HEAD_OK = re.compile(r"^(?:ref: refs/heads/[A-Za-z0-9_./-]+|[0-9a-f]{40}|[0-9a-f]{64})\n?$")
HEX2 = re.compile(r"^[0-9a-f]{2}$")
WALK_CAP = 200000


def git_dir_violations(vault):
    """[(path inside .git, why)]. Reads the directory only: no git is run."""
    g = Path(vault) / ".git"
    bad = []

    def kind(path, want_dir):
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            return "is a symlink"
        if want_dir and not stat.S_ISDIR(st.st_mode):
            return "is not a folder"
        if not want_dir and not stat.S_ISREG(st.st_mode):
            return "is not a regular file"
        return None

    try:
        top = sorted(os.listdir(g))
    except OSError as e:
        return [(".git", f"unreadable ({type(e).__name__})")]
    for name in top:
        if name in GIT_TOP_FILES or name in GIT_TOP_DIRS:
            why = kind(g / name, name in GIT_TOP_DIRS)
            if why:
                bad.append((name, why))
        else:
            bad.append((name, "not part of a plain repository: git may read config, hooks or objects through it"))
    if "HEAD" in top and not kind(g / "HEAD", False):
        try:
            if not HEAD_OK.match((g / "HEAD").read_bytes()[:300].decode("utf-8", "replace")):
                bad.append(("HEAD", "is not a plain branch reference or object id"))
        except OSError:
            bad.append(("HEAD", "unreadable"))
    if "hooks" in top and not kind(g / "hooks", True):
        for n in sorted(os.listdir(g / "hooks")):
            if not n.endswith(".sample") or kind(g / "hooks" / n, False):
                bad.append((f"hooks/{n}", "a hook of yours: core.hooksPath would silently stop it; move it out and adopt again"))
    if "info" in top and not kind(g / "info", True):
        for n in sorted(os.listdir(g / "info")):
            if n not in GIT_INFO_OK or kind(g / "info" / n, False):
                bad.append((f"info/{n}", "git reads it (attributes, grafts, sparse-checkout...): only info/exclude and info/refs are accepted"))
    if "objects" in top and not kind(g / "objects", True):
        for n in sorted(os.listdir(g / "objects")):
            if n in ("pack", "info"):
                why = kind(g / "objects" / n, True)
            elif HEX2.match(n):
                why = kind(g / "objects" / n, True)
            else:
                why = "not an object folder"
            if why:
                bad.append((f"objects/{n}", why))
        if (g / "objects" / "info").is_dir() and not (g / "objects" / "info").is_symlink():
            for n in sorted(os.listdir(g / "objects" / "info")):
                if n not in GIT_OBJECTS_INFO_OK:
                    bad.append((f"objects/info/{n}", "alternates make git read objects from elsewhere"))
    for d in ("refs", "logs"):
        if d in top and not kind(g / d, True):
            seen = 0
            for dirpath, dirs, files in os.walk(g / d):
                for n in dirs + files:
                    seen += 1
                    if os.path.islink(os.path.join(dirpath, n)):
                        bad.append((str(Path(dirpath, n).relative_to(g)), "is a symlink"))
                if seen > WALK_CAP:
                    bad.append((d, "too many entries to verify"))
                    break
    return bad


def unsafe_path(vault, rel):
    """Why writing `rel` under the vault would leave it (a symlink in ANY component, or a non-folder parent), or None."""
    cur = Path(vault)
    for part in Path(rel).parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            return f"{shown_text(cur.relative_to(vault))} is a symlink: adopt would write through it, outside the vault"
        if cur.exists() and not cur.is_dir():
            return f"{shown_text(cur.relative_to(vault))} is not a folder"
    return None


def guard(vault):
    """Everything that must hold before ANY write, judged from disk and from text (no git is run against the vault).
    -> {state, detail, entries, blocking, existing_hook, hook_state}. Called by the plan and again by apply."""
    vault = Path(os.path.abspath(vault))
    state, detail = git_state(vault)
    blocking, entries, existing_hook, hook_state = [], [], None, "create"
    if state == "no-git":
        blocking.append("the vault is not a git repository: run `git init` yourself, then adopt again")
    elif state == "nested":
        blocking.append(f"the vault is inside another git repository ({shown_text(detail)}): adopt needs the vault to be the repo root")
    elif state == "no-binary":
        blocking.append("git is not installed")
    elif state == "unsafe":
        blocking.append(f"unsafe repository layout: {detail}")
    if state == "ok":
        layout = git_dir_violations(vault)
        if layout:
            blocking.append("the .git folder is not a plain repository, so adopt will not run git against this vault ("
                            + "; ".join(f"`.git/{safe(n)}` {why}" for n, why in layout[:8])
                            + "). Point adopt at a clean repository, or clean these up yourself; adopt never edits .git beyond two config keys.")
        entries, violations = read_repo_config(vault)
        if violations:
            blocking.append("the repo's .git/config has content outside the allowlist of what `git init` writes, so adopt "
                            "will not run git against this vault. Read .git/config, remove what is not yours, then adopt again: "
                            + "; ".join(f"entry `{safe(k)}{'' if v is None else ' = ' + safe(v)[:80]}` ({why})" for k, v, why in violations[:8]))
    if not ROOT_SAFE.match(ROOT.as_posix()):
        blocking.append("the path of this cogiforge checkout has characters adopt cannot verify safely: move the checkout")
    for rel in (AREAS, HOOK, BASELINE):
        why = unsafe_path(vault, rel)
        if why:
            blocking.append(why)
    hooks_dir = vault / ".githooks"
    hp = vault / HOOK
    if hooks_dir.is_dir() and not hooks_dir.is_symlink():
        others = sorted(x.name for x in hooks_dir.iterdir() if x.name != "pre-commit")
        if others:
            blocking.append(f".githooks holds other files ({', '.join(shown_text(o) for o in others[:6])}): core.hooksPath would run "
                            "every hook in that folder on git operations. Read them and decide; adopt activates nothing.")
    if hp.exists() or hp.is_symlink():
        if hp.is_file() and not hp.is_symlink() and hp.read_bytes() == HOOK_TEXT.encode("utf-8"):
            hook_state = "identical"
        else:
            hook_state = "foreign"
            try:
                existing_hook = [safe(l)[:200] for l in hp.read_text(encoding="utf-8", errors="replace").splitlines()[:HOOK_PEEK]]
            except OSError:
                existing_hook = ["(could not read it)"]
            blocking.append(f"{HOOK} exists and is NOT the generated hook: it would run on every commit. Read it, "
                            f"then decide (delete or move it, or keep it and wire the cogiforge by hand). Nothing was activated.")
    return {"state": state, "detail": detail, "entries": entries, "blocking": blocking,
            "existing_hook": existing_hook, "hook_state": hook_state}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "area"


def scan(vault):
    """Walks the vault once: {'notes': [rel], 'skipped': [(rel, reason)], 'areas': {folder: n_notes}}."""
    vault = Path(vault)
    notes, skipped, areas = [], [], collections.Counter()
    for dirpath, dirs, names in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in gate.IGNORE_DIRS)
        for fn in sorted(names):
            if not fn.endswith(".md") or fn.startswith("."):
                continue
            p = Path(dirpath) / fn
            rel = p.relative_to(vault).as_posix()
            if p.is_symlink():
                skipped.append((rel, "symlink (never followed)"))
                continue
            try:
                if not stat.S_ISREG(os.lstat(p).st_mode):
                    skipped.append((rel, "not a regular file (pipe, socket or device): never opened"))
                    continue
                if is_dataless(p):
                    skipped.append((rel, "iCloud placeholder not downloaded (dataless)"))
                    continue
                p.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                skipped.append((rel, "not UTF-8"))
                continue
            except OSError as e:
                skipped.append((rel, f"unreadable ({type(e).__name__})"))
                continue
            notes.append(rel)
            parts = Path(rel).parts
            if len(parts) > 1:
                areas[parts[0]] += 1
    return {"notes": notes, "skipped": skipped, "areas": areas}


def infer_areas(counter):
    out = {}
    for folder, n in sorted(counter.items()):
        if (folder.lower() in NOT_AREAS or ":" in folder or n == 0 or folder != folder.strip() or folder[0] in "#;"
                or any(ord(c) < 32 or ord(c) == 127 for c in folder)):  # would inject lines into areas.txt
            continue
        out[folder] = slug(folder)
    return out


def measure(vault, notes):
    """Debt over the readable notes only: orphans, dead wikilinks, missing area:, unparseable frontmatter."""
    vault = Path(vault)
    idx = gate.Index(vault, areas={})
    degree = collections.Counter()
    dead, area_missing, fm_errors = [], [], []
    area_folders = {f for f in infer_areas(collections.Counter(Path(r).parts[0] for r in notes if len(Path(r).parts) > 1))}
    for rel in notes:
        n = gate.Note(vault, vault / rel)
        for target, ln in gate.wikilinks(n.no_code):
            if idx.find(target, rel) is None:
                dead.append(f"{rel}:{ln} [[{target}]]")
        targets = [a for a, _ in gate.wikilinks(n.no_code)] + [unquote(m) for m in ring.MDLINK.findall(n.no_code)]
        for a in targets:
            r = idx.find(a, rel)
            if r and r != rel and r.endswith(".md"):
                degree[rel] += 1
                degree[r] += 1
        parts = Path(rel).parts
        if n.fm_error:
            fm_errors.append(rel)
        elif len(parts) > 1 and parts[0] in area_folders and not str(n.fm.get("area") or "").strip():
            area_missing.append(rel)
    orphans = ring.chk_orphans(notes, degree)
    return {"notes": len(notes), "orphans": orphans, "dead_links": dead, "area_missing": area_missing,
            "frontmatter_errors": fm_errors}


def build_plan(vault):
    vault = Path(os.path.abspath(vault))
    s = scan(vault)
    g = guard(vault)
    state, entries = g["state"], g["entries"]
    areas = infer_areas(s["areas"])
    debt = measure(vault, s["notes"]) if s["notes"] else None
    items, conflicts = [], []
    blocking = list(g["blocking"])

    def item(rel, what):
        if (vault / rel).exists() or (vault / rel).is_symlink():
            conflicts.append(rel)
            items.append({"path": rel, "what": what, "status": "CONFLICT (exists, kept as it is)"})
        else:
            items.append({"path": rel, "what": what, "status": "create"})

    item(AREAS, "proposed areas, one `folder: area` per line")
    if g["hook_state"] == "identical":
        items.append({"path": HOOK, "what": "pre-commit hook (already the generated one)", "status": "identical (kept)"})
    elif g["hook_state"] == "foreign":
        items.append({"path": HOOK, "what": "pre-commit hook", "status": "CONFLICT, NOT ACTIVATED (a different hook)"})
    else:
        items.append({"path": HOOK, "what": "pre-commit hook: ring, gate and leak scan on the notes of the commit",
                      "status": "create"})
    item(BASELINE, "debt measured today, saved as the baseline")
    hooks_path, home_cfg = lookup(entries, "core.hookspath"), lookup(entries, "cogiforge.home")
    items.append({"path": "git config cogiforge.home", "what": f"where the cogiforge checkout lives: {ROOT.as_posix()}",
                  "status": "already set" if home_cfg else "set"})
    if blocking:
        items.append({"path": "git config core.hooksPath", "what": "activate the hook", "status": "NOT set (see pending)"})
    else:
        items.append({"path": "git config core.hooksPath", "what": "activate the hook (value: .githooks)",
                      "status": "already set" if hooks_path == ".githooks" else "set"})
    pending = []
    if not s["notes"]:
        pending.append("nothing to adopt: the vault has no readable note")
        blocking.append(pending[-1])
    pending += [b for b in blocking if b not in pending]
    pending += [f"conflict: {c} already exists, adopt keeps it" for c in conflicts]
    if s["skipped"]:
        pending.append(f"{len(s['skipped'])} note(s) skipped and NOT measured (see the list)")
    return {"vault": str(vault), "git": state, "notes": len(s["notes"]), "skipped": s["skipped"], "areas": areas,
            "items": items, "debt": debt, "pending": pending, "conflicts": conflicts, "blocking": blocking,
            "existing_hook": g["existing_hook"], "hook_text": HOOK_TEXT}


def render(plan):
    out = [f"adopt plan for {plan['vault']}  (dry run: nothing is written)", ""]
    if not plan["notes"]:
        out += ["nothing to adopt: no readable .md note was found here.", ""]
    out.append(f"1. areas inferred from the top-level folders ({len(plan['areas'])}):")
    out += [f"     {f}: {a}" for f, a in plan["areas"].items()] or ["     (none: notes are loose at the root)"]
    out += ["", f"2. install ({plan['git']}):"]
    out += [f"     {i['status']:<34} {i['path']}  -  {i['what']}" for i in plan["items"]]
    d = plan["debt"]
    out += ["", "3. debt measured today (saved as the baseline in " + BASELINE + "):"]
    if d is None:
        out.append("     nothing measured: no readable note")
    else:
        out += [f"     notes measured         {d['notes']}",
                f"     orphan notes           {len(d['orphans'])}   (no link in or out; inbox/ and tasks/ exempt)",
                f"     dead wikilinks         {len(d['dead_links'])}",
                f"     missing area:          {len(d['area_missing'])}   (notes in an area folder)",
                f"     frontmatter not parsed {len(d['frontmatter_errors'])}"]
        for label, key in (("orphans", "orphans"), ("dead links", "dead_links"), ("missing area", "area_missing")):
            for x in d[key][:LIST_CAP]:
                out.append(f"       {label}: {x}")
            if len(d[key]) > LIST_CAP:
                out.append(f"       {label}: ... and {len(d[key]) - LIST_CAP} more (all of them are in the baseline)")
    if plan["skipped"]:
        out += ["", f"   SKIPPED, not measured, not 'fine' ({len(plan['skipped'])}):"]
        out += [f"       {r}: {why}" for r, why in plan["skipped"][:LIST_CAP]]
    out += ["", "4. the hook only judges the notes IN THE COMMIT: the old debt above blocks nobody; it only stops",
            "   new orphans, dead links and personal data from entering. Clean the old debt when you want to.",
            "   (The area check of the gate applies under notes/; elsewhere the area numbers are information.)"]
    if plan["existing_hook"] is not None:
        out += ["", f"the EXISTING {HOOK} is not the generated one. Its first lines (read all of it before deciding):"]
        out += [f"       | {l}" for l in plan["existing_hook"]]
    if plan["git"] == "ok" and plan["existing_hook"] is None:
        out += ["", f"the FULL text of {HOOK} that would be installed (read it: it runs on every commit):", ""]
        out += [f"       | {l}" for l in plan["hook_text"].splitlines()]
    if plan["pending"]:
        out += ["", "pending:"] + [f"   - {p}" for p in plan["pending"]]
    return "\n".join(safe(x) for x in out)


class Blocked(Exception):
    pass


def apply(plan, vault):
    """Writes exactly the plan's `create`/`set` items. Returns the list written."""
    vault = Path(os.path.abspath(vault))
    again = guard(vault)  # the disk may have changed since the plan was printed
    if again["blocking"]:
        raise Blocked(again["blocking"])
    written = []
    d = plan["debt"]
    baseline = {"created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "notes": d["notes"], "orphans": d["orphans"], "dead_links": d["dead_links"],
                "area_missing": d["area_missing"], "frontmatter_errors": d["frontmatter_errors"],
                "skipped": [{"path": r, "reason": w} for r, w in plan["skipped"]]}
    contents = {
        AREAS: "# proposed by tools/adopt.py from your top-level folders; edit freely\n"
               + "".join(f"{f}: {a}\n" for f, a in plan["areas"].items()),
        HOOK: HOOK_TEXT,
        BASELINE: json.dumps(baseline, ensure_ascii=True, indent=2) + "\n",
    }
    # order: the config key first (if git fails, nothing else was written), the files, and the activation LAST
    for i in plan["items"]:
        if i["path"] == "git config cogiforge.home" and i["status"] == "set":
            write_local_config(vault, "cogiforge.home", ROOT.as_posix())
            written.append("git config cogiforge.home")
    for i in plan["items"]:
        rel = i["path"]
        if i["status"] != "create" or rel not in contents:
            continue
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "x", encoding="utf-8", newline="\n") as fh:  # "x": refuses to overwrite even if it appeared meanwhile
            fh.write(contents[rel])
        if rel == HOOK:
            p.chmod(0o755)
        written.append(rel)
    for i in plan["items"]:
        if i["path"] == HOOK and i["status"] == "identical (kept)":
            (vault / HOOK).chmod(0o755)  # same bytes as ours; only makes sure git can run it
    for i in plan["items"]:
        if i["path"] == "git config core.hooksPath" and i["status"] == "set":
            write_local_config(vault, "core.hooksPath", ".githooks")
            written.append("git config core.hooksPath")
    return written


def run(args):
    vault = Path(os.path.abspath(args.vault))
    if not vault.is_dir():
        emit(f"ERROR: vault is not a folder or unreadable: {vault}", file=sys.stderr)
        return 3
    plan = build_plan(vault)
    if args.json:
        emit(json.dumps(plan, ensure_ascii=True, indent=2))
    else:
        emit(render(plan))
    if not args.apply:
        return 1 if plan["pending"] else 0
    # --apply: the plan is already on the screen
    if plan["blocking"]:
        emit("\nNOT APPLIED, nothing was written: " + "; ".join(plan["blocking"]), file=sys.stderr)
        return 1
    if not args.yes:
        if not sys.stdin.isatty():
            emit("\nNOT APPLIED: --apply needs --yes (or an interactive terminal). Nothing was written.", file=sys.stderr)
            return 2
        if input("\nApply this plan? Type 'yes': ").strip().lower() != "yes":
            emit("NOT APPLIED: no confirmation. Nothing was written.", file=sys.stderr)
            return 2
    try:
        written = apply(plan, vault)
    except Blocked as e:
        emit("\nNOT APPLIED, the vault changed since the plan and now fails: " + "; ".join(e.args[0]), file=sys.stderr)
        return 1
    except (subprocess.CalledProcessError, OSError) as e:
        emit(f"\nAPPLY FAILED ({type(e).__name__}); some files may have been written, see `git status` in the vault. "
             "Nothing was activated unless it is listed above.", file=sys.stderr)
        return 1
    after = guard(vault)  # what was just written must still pass: catches a vault that changed during the apply
    if after["blocking"]:
        emit("\nWARNING: the vault changed while adopt was writing and now fails its checks: " + "; ".join(after["blocking"]),
             file=sys.stderr)
        return 1
    emit("\nAPPLIED:" + "".join(f"\n   {w}" for w in written or ["(nothing to create: everything existed)"]))
    emit("Existing notes were not touched. Test it: add a note with no link and run git commit.")
    return 1 if plan["pending"] else 0


def selftest():
    results = []

    def check(label, ok):
        results.append(ok)
        emit(("ok   " if ok else "FAIL ") + label)

    def call(*argv):
        keep, sys.stdin = sys.stdin, io.StringIO("")  # never a tty: the selftest must not wait for an answer
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return run(parser().parse_args(list(argv)))
        finally:
            sys.stdin = keep

    def snap(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*")
                if p.is_file() and ".git/" not in p.as_posix()}

    with tempfile.TemporaryDirectory() as td:
        v = Path(td) / "v"
        for rel, txt in {"Ideas/a.md": "---\narea: ideas\n---\nsee [[b]]\n", "Ideas/b.md": "back to [[a]] and [[ghost]]\n",
                         "Work/c.md": "alone\n", ".obsidian/app.json": "{}"}.items():
            (v / rel).parent.mkdir(parents=True, exist_ok=True)
            (v / rel).write_text(txt, encoding="utf-8")
        before = snap(v)
        plan = build_plan(v)
        check("areas ignore .obsidian", sorted(plan["areas"]) == ["Ideas", "Work"])
        check("debt: 1 orphan, 1 dead link, 2 without area:",
              (len(plan["debt"]["orphans"]), len(plan["debt"]["dead_links"]), len(plan["debt"]["area_missing"])) == (1, 1, 2))
        check("dry run writes nothing", call(str(v)) == 1 and snap(v) == before)
        check("not a git repo: --apply is pending, rc 1, writes nothing",
              call(str(v), "--apply", "--yes") == 1 and snap(v) == before and not (v / ".git").exists())
        subprocess.run(["git", "init", "-q"], cwd=v, check=True)
        before = snap(v)
        check("--apply without --yes (no tty): rc 2, writes nothing", call(str(v), "--apply") == 2 and snap(v) == before)
        check("--apply --yes: rc 0", call(str(v), "--apply", "--yes") == 0)
        check("hook and baseline exist", (v / HOOK).is_file() and (v / BASELINE).is_file() and not (v / '.cogiforge' / 'home').exists())
        check("existing notes are byte for byte the same",
              all(snap(v)[k] == b for k, b in before.items() if k.endswith(".md")))
        (v / AREAS).write_text("mine: mine\n")
        check("existing areas.txt is kept (conflict, rc 1)",
              call(str(v), "--apply", "--yes") == 1 and (v / AREAS).read_text() == "mine: mine\n")
        empty = Path(td) / "empty"
        (empty / ".obsidian").mkdir(parents=True)
        check("empty vault: rc 1, 'nothing to adopt'", call(str(empty)) == 1
              and "nothing to adopt" in render(build_plan(empty)))
    emit("selftest: " + ("OK" if all(results) else "FAILED"))
    return 0 if all(results) else 1


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vault", nargs="?")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    ap = parser()
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.vault:
        ap.print_usage(sys.stderr)
        return 2
    if args.yes and not args.apply:
        emit("ERROR: --yes only makes sense with --apply", file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
