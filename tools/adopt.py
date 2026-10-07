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

Trust model: the vault may come from outside, so adopt runs NO git to inspect it: it reads `.git/config` as text and
refuses (blocking, rc 1, nothing written) if it names commands git would run (core.fsmonitor, sshCommand, pager, editor,
`!` aliases, filter/diff/merge/credential commands, an `include`, a core.hooksPath other than `.githooks`), if `.git`,
`.git/config`, `.githooks` or `.cogiforge` is a symlink or the wrong kind of file, or if `.git` is a file. It only runs
git to WRITE two local keys, after those checks. Notes that are pipes or devices are never opened. The one thing it
trusts is YOUR choice of checkout: `cogiforge.home` is checked for the three scripts, not for who wrote them, so point
it only at a cogiforge you cloned yourself and keep that folder writable by you alone.

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
# Deliberate bypass: git commit --no-verify

root=$(git rev-parse --show-toplevel) || exit 1
cd "$root" || exit 1
home=$(git config --local --get cogiforge.home)
block() { echo "  COMMIT BLOCKED: $1" >&2; echo "  Fix: git config --local cogiforge.home <absolute path of your cogiforge checkout>" >&2; exit 1; }
case "$home" in
    /*) ;;
    *) block "cogiforge.home is not set to an absolute path." ;;
esac
[ -d "$home" ] || block "cogiforge.home is not a folder."
for f in core/gate.py core/ring.py core/leak.py; do
    [ -f "$home/$f" ] || block "cogiforge.home does not contain $f."
done
out=$(mktemp) || exit 1
trap 'rm -f "$out"' EXIT
blocked=0

if git diff --cached --name-only --diff-filter=ACMR | grep -q '\\.md$'; then
    if ! python3 "$home/core/ring.py" --vault . --gate --stage >"$out" 2>&1; then
        echo "  COMMIT BLOCKED: a note in this commit has no link"
        sed 's/^/     /' "$out" | head -20
        blocked=1
    fi
    if ! git diff --cached --name-only --diff-filter=ACMR -z -- '*.md' | xargs -0 python3 "$home/core/gate.py" --vault . -- >"$out" 2>&1; then
        echo "  COMMIT BLOCKED: a note in this commit fails the gate"
        sed 's/^/     /' "$out" | head -20
        blocked=1
    fi
fi

if ! python3 "$home/core/leak.py" --staged >"$out" 2>&1; then
    echo "  COMMIT BLOCKED: personal data in what is going into the commit"
    sed 's/^/     /' "$out" | head -20
    blocked=1
fi

[ "$blocked" -eq 0 ] || { echo "  Deliberate bypass: git commit --no-verify"; exit 1; }
exit 0
"""


def is_dataless(path):
    """iCloud placeholder that is not downloaded: no blocks on disk, but a size."""
    st = os.lstat(path)
    return st.st_blocks == 0 and st.st_size > 0


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


BOOL = {"true", "false", "yes", "no", "on", "off", "0", "1", ""}
# (section, key) pairs whose value is a command git may run; None = any key of that section
RISKY = {("core", "sshcommand"), ("core", "pager"), ("core", "editor"), ("core", "askpass"), ("core", "gitproxy"),
         ("sequence", "editor"), ("gpg", "program"), ("credential", "helper"), ("diff", "external"),
         ("diff", "command"), ("diff", "textconv"), ("merge", "driver"), ("filter", "clean"), ("filter", "smudge"),
         ("filter", "process"), ("pager", None), ("include", None), ("includeif", None), ("difftool", "cmd"),
         ("mergetool", "cmd"), ("man", "cmd"), ("uploadpack", "packobjectshook"), ("remote", "vcs"),
         ("remote", "receivepack"), ("remote", "uploadpack"), ("http", "sslcommand")}
CONFIG_LINE = re.compile(r'^\[\s*([A-Za-z0-9-]+)((?:\.[^\s"\]]+)?)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\](.*)$')


def parse_git_config(text):
    """[(section, subsection, key, value)], lowercased section and key. Reads text only: no git, no includes."""
    out, sect = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        m = CONFIG_LINE.match(line)
        if m:
            sect = (m.group(1).lower(), (m.group(2)[1:] or m.group(3) or ""))
            line = m.group(4).strip()
            if not line or line[0] in "#;":
                continue
        if sect is None:
            continue
        k, eq, v = line.partition("=")
        out.append((sect[0], sect[1], k.strip().lower(), v.strip().strip('"') if eq else "true"))
    return out


def risky_entries(entries):
    """The entries of a repo config that make git (or the hook) run a command, or pull in another config file."""
    found = []
    for sec, sub, key, val in entries:
        name = f"{sec}.{sub + '.' if sub else ''}{key}"
        if (sec, key) in RISKY or (sec, None) in RISKY:
            found.append((name, val))
        elif sec == "core" and key == "fsmonitor" and val.lower() not in BOOL:
            found.append((name, val))
        elif sec == "core" and key == "hookspath" and val not in ("", ".githooks"):
            found.append((name, val))
        elif sec == "alias" and val.startswith("!"):
            found.append((name, val))
    return found


def read_repo_config(vault):
    """(entries, error). The local config of the repo, read as text."""
    cfg = Path(vault) / ".git" / "config"
    if cfg.is_symlink():
        return [], ".git/config is a symlink"
    if not cfg.exists():
        return [], None
    if not cfg.is_file():
        return [], ".git/config is not a regular file"
    try:
        return parse_git_config(cfg.read_text(encoding="utf-8", errors="replace")), None
    except OSError as e:
        return [], f".git/config unreadable ({type(e).__name__})"


def safe_git(vault, *args):
    """git with the vault's own config unable to run anything on the way: only used to WRITE two keys."""
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-C", str(vault), *args],
                          capture_output=True, text=True, env=env, check=True)


def lookup(entries, section, key):
    vals = [v for sec, sub, k, v in entries if sec == section and not sub and k == key]
    return vals[-1] if vals else ""


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
        if folder.lower() in NOT_AREAS or ":" in folder or n == 0:
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
    vault = Path(vault)
    s = scan(vault)
    state, top = git_state(vault)
    entries, cfg_error = read_repo_config(vault) if state == "ok" else ([], None)
    areas = infer_areas(s["areas"])
    debt = measure(vault, s["notes"]) if s["notes"] else None
    items, conflicts, blocking = [], [], []

    def item(rel, what):
        if (vault / rel).exists() or (vault / rel).is_symlink():
            conflicts.append(rel)
            items.append({"path": rel, "what": what, "status": "CONFLICT (exists, kept as it is)"})
        else:
            items.append({"path": rel, "what": what, "status": "create"})

    risky = risky_entries(entries)
    for d_name in (".githooks", ".cogiforge"):
        dp = vault / d_name
        if dp.is_symlink() or (dp.exists() and not dp.is_dir()):
            blocking.append(f"{d_name} is a symlink or not a folder: adopt would write through it, outside the vault.")
    if cfg_error:
        blocking.append(cfg_error + ": adopt will not run git against it.")
    if risky:
        blocking.append("the repo's .git/config names commands git would run or files it would include: "
                        + "; ".join(f"{n} = {v[:60]}" for n, v in risky)
                        + ". Read .git/config, remove what is not yours, then adopt again. Nothing was written and no git was run.")

    hook_ok, existing_hook = True, None
    item(AREAS, "proposed areas, one `folder: area` per line")
    hp = vault / HOOK
    if hp.exists() or hp.is_symlink():
        if hp.is_file() and not hp.is_symlink() and hp.read_bytes() == HOOK_TEXT.encode("utf-8"):
            items.append({"path": HOOK, "what": "pre-commit hook (already the generated one)", "status": "identical (kept)"})
        else:
            hook_ok = False
            try:
                existing_hook = hp.read_text(encoding="utf-8", errors="replace").splitlines()[:HOOK_PEEK]
            except OSError:
                existing_hook = ["(could not read it)"]
            items.append({"path": HOOK, "what": "pre-commit hook", "status": "CONFLICT, NOT ACTIVATED (a different hook)"})
            blocking.append(f"{HOOK} exists and is NOT the generated hook: it would run on every commit. Read it, "
                            f"then decide (delete or move it, or keep it and wire the cogiforge by hand). Nothing was activated.")
    else:
        items.append({"path": HOOK, "what": "pre-commit hook: ring, gate and leak scan on the notes of the commit",
                      "status": "create"})
    item(BASELINE, "debt measured today, saved as the baseline")
    hooks_path = home_cfg = ""
    if state == "ok":
        hooks_path = lookup(entries, "core", "hookspath")
        home_cfg = lookup(entries, "cogiforge", "home")
    if home_cfg and home_cfg != str(ROOT):
        items.append({"path": "git config cogiforge.home", "what": "where the cogiforge checkout lives",
                      "status": f"CONFLICT (already set to another path, kept as it is)"})
        blocking.append("`cogiforge.home` is already set to a different path in this repo's git config: the hook would "
                        "run code from there. Check it (`git config --local cogiforge.home`) and unset it if it is not yours.")
    else:
        items.append({"path": "git config cogiforge.home", "what": f"where the cogiforge checkout lives: {ROOT}",
                      "status": "set" if not home_cfg else "already set"})
    if not hook_ok:
        items.append({"path": "git config core.hooksPath", "what": "activate the hook", "status": "NOT set (see the hook conflict)"})
    elif hooks_path and hooks_path != ".githooks":
        conflicts.append("git config core.hooksPath")
        items.append({"path": "git config core.hooksPath", "what": "activate the hook",
                      "status": f"CONFLICT (already '{hooks_path}', kept as it is)"})
    else:
        items.append({"path": "git config core.hooksPath", "what": "activate the hook (value: .githooks)",
                      "status": "set" if hooks_path != ".githooks" else "already set"})
    pending = []
    if not s["notes"]:
        pending.append("nothing to adopt: the vault has no readable note")
        blocking.append(pending[-1])
    if state == "no-git":
        pending.append("the vault is not a git repository: run `git init` yourself, then adopt again")
    elif state == "nested":
        pending.append(f"the vault is inside another git repository ({top}): adopt needs the vault to be the repo root")
    elif state == "no-binary":
        pending.append("git is not installed")
    elif state == "unsafe":
        pending.append(f"unsafe repository layout: {top}")
    if state != "ok":
        blocking.append(pending[-1])
    pending += [b for b in blocking if b not in pending]
    pending += [f"conflict: {c} already exists, adopt keeps it" for c in conflicts]
    if s["skipped"]:
        pending.append(f"{len(s['skipped'])} note(s) skipped and NOT measured (see the list)")
    return {"vault": str(vault), "git": state, "notes": len(s["notes"]), "skipped": s["skipped"], "areas": areas,
            "items": items, "debt": debt, "pending": pending, "conflicts": conflicts, "blocking": blocking,
            "existing_hook": existing_hook, "hook_text": HOOK_TEXT}


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
    return "\n".join(out)


def apply(plan, vault):
    """Writes exactly the plan's `create`/`set` items. Returns the list written."""
    vault = Path(vault)
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
        BASELINE: json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
    }
    for i in plan["items"]:
        rel = i["path"]
        if i["status"] != "create" or rel not in contents:
            continue
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "x", encoding="utf-8") as fh:  # "x": refuses to overwrite even if it appeared meanwhile
            fh.write(contents[rel])
        if rel == HOOK:
            p.chmod(0o755)
        written.append(rel)
    for i in plan["items"]:
        if i["path"] == HOOK and i["status"] == "identical (kept)":
            (vault / HOOK).chmod(0o755)  # same bytes as ours; only makes sure git can run it
    for i in plan["items"]:
        if i["path"] == "git config cogiforge.home" and i["status"] == "set":
            safe_git(vault, "config", "--local", "cogiforge.home", str(ROOT))
            written.append("git config cogiforge.home")
    for i in plan["items"]:
        if i["path"] == "git config core.hooksPath" and i["status"] == "set":
            safe_git(vault, "config", "--local", "core.hooksPath", ".githooks")
            written.append("git config core.hooksPath")
    return written


def run(args):
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"ERROR: vault is not a folder or unreadable: {vault}", file=sys.stderr)
        return 3
    plan = build_plan(vault)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(render(plan))
    if not args.apply:
        return 1 if plan["pending"] else 0
    # --apply: the plan is already on the screen
    if plan["blocking"]:
        print("\nNOT APPLIED, nothing was written: " + "; ".join(plan["blocking"]), file=sys.stderr)
        return 1
    if not args.yes:
        if not sys.stdin.isatty():
            print("\nNOT APPLIED: --apply needs --yes (or an interactive terminal). Nothing was written.", file=sys.stderr)
            return 2
        if input("\nApply this plan? Type 'yes': ").strip().lower() != "yes":
            print("NOT APPLIED: no confirmation. Nothing was written.", file=sys.stderr)
            return 2
    written = apply(plan, vault)
    print("\nAPPLIED:" + "".join(f"\n   {w}" for w in written or ["(nothing to create: everything existed)"]))
    print("Existing notes were not touched. Test it: add a note with no link and run git commit.")
    return 1 if plan["pending"] else 0


def selftest():
    results = []

    def check(label, ok):
        results.append(ok)
        print(("ok   " if ok else "FAIL ") + label)

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
    print("selftest:", "OK" if all(results) else "FAILED")
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
    ap = parser()
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.vault:
        ap.print_usage(sys.stderr)
        return 2
    if args.yes and not args.apply:
        print("ERROR: --yes only makes sense with --apply", file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
