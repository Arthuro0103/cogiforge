#!/usr/bin/env python3
"""mutate.py: kills each check of each piece, one at a time, and demands a red suite.

Two operators:
  chk     injects `return []` as the 1st line of every `def chk_*` (the check never fails again);
  text    swaps an exact snippet for another (a behavior that is not `chk_`: ignoring
          `blocklist.txt`, the inbox exemption, the hook's `exit 1`...). The snippet has to exist
          ONCE; if it does not, the mutant is "inapplicable" and counts as a tool failure.

An equal score proves nothing: the script prints the NAME of the tests that fail, clears the bytecode
every round and runs with PYTHONDONTWRITEBYTECODE=1.

    python3 tests/mutate.py                 all pieces
    python3 tests/mutate.py leak ring       only these
    python3 tests/mutate.py --dry           only checks that each mutant applies (seconds, no suite)
rc: 0 every mutant dead · 1 a mutant survived · 2 suite already red / inapplicable mutant
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PIECES = {
    "leak": dict(file="core/leak.py", suite=["tests/test_leak.py"], texts=[
        ("ignores blocklist files", 'if text is None or Path(name).name in BLOCKLIST_NAMES:', 'if text is None:'),
        ("ignores .leakignore", 'if os.path.normpath(name) in ignored:', 'if False:'),
        ("require-list does not fail", 'return 3', 'return 0'),
        ("finding does not fail", 'return 1 if total else (2 if unreadable else 0)', 'return 0'),
        ("absence becomes OK", 'print("NOT_VERIFIED:', 'print("OK:'),
        ("list is case-sensitive", 'lowered = line.casefold()', 'lowered = line'),
        ("blocklist does not skip comments", ' and not t.lstrip().startswith("#")', ''),
        ("scans .git", 'SKIP_DIRS = {".git", ', 'SKIP_DIRS = {'),
        ("echoes the data", 'print(f"{name}:{n}: {kind}")', 'print(f"{name}:{n}: {kind} {text.splitlines()[n-1]}")'),
        ("no NFKC", 'unicodedata.normalize("NFKC", text)', 'text'),
        ("zero-width stays", 'if unicodedata.category(c) != "Cf")', 'if True)'),
        ("path is case-sensitive", '[A-Za-z0-9._-]+", re.IGNORECASE)', '[A-Za-z0-9._-]+")'),
        ("private list in the stage passes", '(args.staged or os.path.normpath(name) in versioned)', 'os.path.normpath(name) in versioned'),
        ("unreadable becomes clean", 'return 1 if total else (2 if unreadable else 0)', 'return 1 if total else 0'),
        ("utf-16 skipped", 'return data.decode("utf-16", errors="replace")', 'return None'),
        ("invalid utf-8 skipped", 'return data.decode("utf-8", errors="replace")', 'return None'),
        ("example.com.br exempt", '(?:com|org|net)(?![\\w-]|\\.\\w))', '(?:com|org|net)\\b)'),
        ("e-mail with ':' exempt", 'm.group(1) in SCP_USERS and line', 'True and line'),
        ("empty list becomes verified", 'return terms or None', 'return terms'),
        ("missing path passes", 'if missing:', 'if False:'),
        ("venv exempt", '".pytest_cache"}', '".pytest_cache", "venv"}'),
        ("versioned private list passes", '(args.staged or os.path.normpath(name) in versioned)', 'args.staged'),
        ("silent exemption", 'exempted.append(name)', 'pass'),
        ("example.com e-mail leaks", r'(?!example\.(?:com|org|net)(?![\w-]|\.\w))', ''),
        ("old private list name not read", 'if not BLOCKLIST_DEFAULT.is_file() and LEGACY_BLOCKLIST_DEFAULT.is_file():', 'if False:'),
        ("old private list name without a warning", 'WARNING: the private list was renamed', 'the private list was renamed'),
        ("old env var not read", 'if os.environ.get("VAZAMENTO_NEGRA"):', 'if False:'),
        ("old env var without a warning", 'WARNING: env VAZAMENTO_NEGRA is the old name', 'env VAZAMENTO_NEGRA is the old name'),
        ("new env var does not win", 'if os.environ.get("LEAK_BLOCKLIST"):', 'if False:'),
        ("negra.txt not ignored by the scanner", 'BLOCKLIST_NAMES = (BLOCKLIST_NAME, LEGACY_BLOCKLIST_NAME)', 'BLOCKLIST_NAMES = (BLOCKLIST_NAME,)'),
        ("blocklist.txt not ignored by the scanner", 'BLOCKLIST_NAMES = (BLOCKLIST_NAME, LEGACY_BLOCKLIST_NAME)', 'BLOCKLIST_NAMES = (LEGACY_BLOCKLIST_NAME,)'),
    ]),
    "gate": dict(file="core/gate.py", suite=["tests/test_gate.py", "tests/test_demo.py"], texts=[
        ("area: folder != area passes", 'if area != expected:', 'if False:'),
        ("frontmatter of tasks is judged by the subset", ' or Path(n.rel).parts[0] in PLUGIN_FOLDERS', ''),
        ("file outside the vault passes", 'f.resolve().relative_to(vault.resolve())', 'f.resolve().relative_to(f.resolve())'),
        ("area: outside the list passes", 'if area not in areas.values():', 'if False:'),
        ("area: unknown folder passes", 'if expected is None:', 'if False:'),
        ("area: missing field passes", 'if area is None or not str(area).strip():', 'if False:'),
        ("area: loose note passes", 'if len(parts) < 3:', 'if False:'),
        ("area: counts twice with frontmatter", 'if n.fm_error:\n        return []  # already failed', 'if False:\n        return []  # already failed'),
        ("area: applies outside notes/", 'if parts[0] != "notes":', 'if False:'),
        ("fm: tab accepted", r'if "\t" in s[:len(s) - len(s.lstrip())]:', 'if False:'),
        ("fm: colon without quotes accepted", 'if ": " in v or v.endswith(":"):', 'if False:'),
        ("fm: open quotes accepted", 'if len(v) < 2 or v[-1] != v[0]:', 'if False:'),
        ("fm: open list accepted", 'if not v.endswith("]"):', 'if False:'),
        ("fm: block text accepted", 'if v[:1] in "{|>&*!%@`":', 'if False:'),
        ("fm: comment at the end would stay in the value", r'v = re.sub(r"\s+#.*$", "", v)', 'v = v'),
        ("fm: nested map accepted", 'if not item or last is None:', 'if False:'),
        ("fm: item over a scalar accepted", 'if not isinstance(d[last], list):', 'if False:'),
        ("fm: line without a key accepted", 'if not m:\n                raise', 'if False:\n                raise'),
        ("fm: open without closing passes", 'return None, (1, "opens with --- and never closes")', 'return None, None'),
        ("link: relative layer", 'if r.lower() in self.paths:', 'if False:'),
        ("link: path suffix", 'if lower.endswith("/" + c.lower()):', 'if False:'),
        ("link: name only matches with exact case", 'n = target.lower() if has_ext else target.lower() + ".md"', 'n = target if has_ext else target + ".md"'),
        ("mask: fence closes early", 'if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and line.strip() == m.group(1):', 'if m:'),
        ("mask: inline becomes a link", 'out.append(INLINE.sub(lambda x: " " * len(x.group(0)), line))', 'out.append(line)'),
        ("link: anchor stays in the target", 'return re.split(r"[#^]", target, maxsplit=1)[0].strip()', 'return target.strip()'),
        ("target: none becomes dead", ' or a.lower() == "none":', ':'),
        ("target: name with a path matches by suffix", 'or ("/" not in a and idx.find(a, n.rel) is not None)', 'or idx.find(a, n.rel) is not None'),
        ("target: bare name never resolves", 'or ("/" not in a and idx.find(a, n.rel) is not None)', ''),
        ("scans tool folders (index)", 'dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)\n            for fn in sorted(names):', 'dirs[:] = sorted(dirs)\n            for fn in sorted(names):'),
        ("scans tool folders (collect)", 'dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)\n            found +=', 'dirs[:] = sorted(dirs)\n            found +='),
        ("unreadable does not exit 3", 'return 3 if unreadable else (1 if failures else 0)', 'return 1 if failures else 0'),
        ("failure does not exit 1", 'return 3 if unreadable else (1 if failures else 0)', 'return 3 if unreadable else 0'),
        ("--check does not filter", 'if not checks or f.check in checks', 'if True'),
        ("unknown check accepted", 'or (args.check and set(args.check) - names)', ''),
        ("non-utf8 read as text", 'except (OSError, UnicodeDecodeError) as e:', 'except OSError as e:'),
        ("broken-link counts the whole line", 'if "[[" in rest:', 'if "[[" in line:'),
    ]),
    "ring": dict(file="core/ring.py", suite=["tests/test_ring.py", "tests/test_demo.py"], texts=[
        ("inbox and tasks stop being exempt", 'DEPOSITS = ("inbox", "tasks")', 'DEPOSITS = ()'),
        ("tasks stops being exempt", 'DEPOSITS = ("inbox", "tasks")', 'DEPOSITS = ("inbox",)'),
        ("inbox stops being exempt", 'DEPOSITS = ("inbox", "tasks")', 'DEPOSITS = ("tasks",)'),
        ("inbox exempt by prefix", 'rel == d or rel.startswith(d + "/")', 'rel.startswith(d)'),
        ("self-link is an edge", 'if r and r != rel and r.endswith(".md"):', 'if r and r.endswith(".md"):'),
        ("link to an image is an edge", 'if r and r != rel and r.endswith(".md"):', 'if r and r != rel:'),
        ("inbound does not count", '                degree[r] += 1\n', '                pass\n'),
        ("outbound does not count", '                degree[rel] += 1\n', '                pass\n'),
        ("markdown link is not an edge", ' + [unquote(m) for m in MDLINK.findall(text)]', ''),
        ("markdown link without unquote", 'unquote(m) for m in', 'm for m in'),
        ("code becomes an edge", 'text = mask(Path(vault, rel).read_bytes().decode("utf-8", errors="replace"))', 'text = Path(vault, rel).read_bytes().decode("utf-8", errors="replace")'),
        ("stage without NFC", 'if nfc(r) in in_commit', 'if r in in_commit'),
        ("stage: warning vanishes", 'if outside:', 'if False:'),
        ("stage: missing git becomes ok", 'print("NOT_VERIFIED: could not read the git stage', 'return 0; print("NOT_VERIFIED: could not read the git stage'),
        ("missing vault becomes ok", 'if not Path(vault).is_dir():\n        print(f"NOT_VERIFIED', 'if False:\n        print(f"NOT_VERIFIED'),
        ("message does not teach", 'How to fix: open', 'open'),
        ("selftest always ok", 'return 1 if failed else 0', 'return 0'),
        ("selftest does not plant an orphan", r'write("loose.md", "no link here\n")', r'write("loose.md", "linked to [[a]]\n")'),
        ("--stage ignored in the CLI", 'return gate(args.vault, stage_only=args.stage)', 'return gate(args.vault)'),
    ]),
    "hook": dict(file=".githooks/pre-commit", suite=["tests/test_hook_e2e.py"], texts=[
        ("ring does not run", 'python3 core/ring.py --vault vault --gate --stage', 'true'),
        ("ring looks at the whole vault", '--gate --stage', '--gate'),
        (".md filter vanishes", "grep -q '\\.md$'", "grep -q 'ZZZ'"),
        ("ring does not block", "head -20\n        blocked=1\n    elif", "head -20\n    elif"),
        ("ring warning vanishes", "elif grep -q '^WARNING' \"$out\"; then", "elif false; then"),
        ("leak does not run", 'python3 core/leak.py --staged', 'true'),
        ("leak does not block", "    blocked=1\nelif", "elif"),
        ("NOT_VERIFIED vanishes", "elif grep -q 'NOT_VERIFIED' \"$out\"; then", "elif false; then"),
        ("leak rename warning vanishes", "grep '^WARNING' \"$out\" | sed 's/^/  /' || true", "true"),
        ("always exits 0", '[ "$blocked" -eq 0 ] || {', 'true || {'),
        ("incomplete installation passes", 'if [ ! -f "$f" ]; then', 'if false; then'),
    ]),
    "install": dict(file="install.sh", suite=["tests/test_hook_e2e.py"], texts=[
        ("does not activate hooksPath", 'git config core.hooksPath .githooks || fail', 'true || fail'),
        ("old python passes", '    || fail "Python 3.10 or newer is required; found $(python3 -V 2>&1)."', '    || true'),
        ("broken selftest passes", '    || { python3 core/ring.py --selftest >&2; fail "the ring selftest failed: the gate does not catch an orphan."; }', '    || true'),
        ("outside a git repo passes", "    || fail \"this is not a git repository. Use 'git clone', not the zip, or run 'git init' here.\"", '    || true'),
    ]),
}


def checks(source):
    return re.findall(r"^def (chk_\w+)\(", source, re.M)


def mutate_chk(source, target):
    pattern = re.compile(rf"(^def {re.escape(target)}\([^)]*\)[^:\n]*:\n)((?:\s*(?:\"\"\".*?\"\"\"|'''.*?''')\n)?)",
                         re.M | re.S)
    m = pattern.search(source)
    if not m:
        raise LookupError(target)
    return source[:m.end()] + "    return []  # MUTANT\n" + source[m.end():]


def mutate_text(source, old, new):
    if source.count(old) != 1:
        raise LookupError(f"{old!r} appears {source.count(old)}x")
    return source.replace(old, new)


def run_suite(suite):
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", *suite, "-q", "--no-header", "-x",
                        "-p", "no:cacheprovider", "-W", "ignore"],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    failed = sorted(set(re.findall(r"^FAILED\s+\S*::(\S+)", r.stdout, re.M)))
    return r.returncode, failed


def mutants(piece, source):
    for c in checks(source):
        yield f"chk:{c}", lambda f, c=c: mutate_chk(f, c)
    for name, old, new in PIECES[piece]["texts"]:
        yield f"text:{name}", lambda f, a=old, n=new: mutate_text(f, a, n)


def dry(targets):
    """Only checks that each mutant applies (the snippet exists ONCE), without running the suite.

    Takes seconds. Run it before each commit of a rename: a message or a name that changed
    leaves the mutant inapplicable, and it shows up here instead of only at the end, in the
    full round."""
    total, inapplicable = 0, []
    for piece in targets:
        file = ROOT / PIECES[piece]["file"]
        if not file.exists():
            print(f"[{piece}] {PIECES[piece]['file']} does not exist yet — skipped")
            continue
        original = file.read_text(encoding="utf-8")
        for name, fn in mutants(piece, original):
            try:
                fn(original)
                total += 1
            except LookupError as e:
                inapplicable.append(f"{piece}/{name}")
                print(f"  INAPPLICABLE {name}: {e}")
    print(f"{total} mutants apply; {len(inapplicable)} inapplicable")
    return 2 if inapplicable else 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    targets = args or list(PIECES)
    if "--dry" in sys.argv:
        return dry(targets)
    alive, inapplicable, total = [], [], 0
    for piece in targets:
        spec = PIECES[piece]
        file = ROOT / spec["file"]
        if not file.exists():
            print(f"[{piece}] {spec['file']} does not exist yet — skipped")
            continue
        original = file.read_text(encoding="utf-8")
        rc, _ = run_suite(spec["suite"])
        if rc != 0:
            print(f"[{piece}] the suite is already RED without mutation — fix it before mutating.")
            return 2
        print(f"[{piece}] baseline green")
        try:
            for name, fn in mutants(piece, original):
                try:
                    new = fn(original)
                except LookupError as e:
                    inapplicable.append(f"{piece}/{name}")
                    print(f"  INAPPLICABLE {name}: {e}")
                    continue
                total += 1
                file.write_text(new, encoding="utf-8")
                rc, failed = run_suite(spec["suite"])
                if rc == 0:
                    alive.append(f"{piece}/{name}")
                    print(f"  SURVIVED    {name}")
                else:
                    print(f"  dead        {name:45} {', '.join(failed[:2]) or '(no name captured)'}")
        finally:
            file.write_text(original, encoding="utf-8")
    print(f"\n{total - len(alive)} of {total} mutants dead; {len(alive)} alive; {len(inapplicable)} inapplicable")
    for v in alive:
        print("  alive:", v)
    return 2 if inapplicable else (1 if alive else 0)


if __name__ == "__main__":
    sys.exit(main())
