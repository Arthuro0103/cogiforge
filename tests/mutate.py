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
Each suite run has a time limit (SUITE_TIMEOUT, 300 s) and never inherits the terminal's stdin. A mutant whose
suite does not finish in time (a hang is a suite that did not stay green) counts as DEAD and is reported as
`killed (timeout)` with the mutant's name; the whole process group is killed so no child is left behind (a mutant that only makes the suite slow shows up as
`killed (timeout)`, not as a survivor). Ctrl-C, SIGTERM and SIGHUP kill the suite that is running before mutate.py exits.
Without `os.killpg` (Windows) only the suite process itself is killed.
The baseline run (no mutation) that times out is "already red": rc 2.
rc: 0 every mutant dead · 1 a mutant survived · 2 suite already red / inapplicable mutant
"""
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE_TIMEOUT = 300  # seconds per suite run
TIMEOUT_RC = -999   # run_suite's return code when the time ran out

PIECES = {
    "leak": dict(file="core/leak.py", suite=["tests/test_leak.py"], texts=[
        ("ignores blocklist files", 'if text is None or Path(name).name in BLOCKLIST_NAMES:', 'if text is None:'),
        ("ignores .leakignore", 'if os.path.normpath(name) in ignored:', 'if False:'),
        ("require-list does not fail", 'return 3', 'return 0'),
        ("finding does not fail", 'return 1 if total else (2 if (unreadable or index_failed) else 0)', 'return 0'),
        ("absence becomes OK", 'print("NOT_VERIFIED:', 'print("OK:'),
        ("list is case-sensitive", 'lowered = line.casefold()', 'lowered = line'),
        ("blocklist does not skip comments", ' and not t.lstrip().startswith("#")', ''),
        ("scans .git", 'SKIP_DIRS = {".git", ', 'SKIP_DIRS = {'),
        ("echoes the data", 'print(f"{shown(name)}:{n}: {kind}")', 'print(f"{shown(name)}:{n}: {kind} {text.splitlines()[n-1]}")'),
        ("no NFKC", 'unicodedata.normalize("NFKC", text)', 'text'),
        ("zero-width stays", 'if unicodedata.category(c) != "Cf")', 'if True)'),
        ("path is case-sensitive", '[A-Za-z0-9._-]+", re.IGNORECASE)', '[A-Za-z0-9._-]+")'),
        ("private list in the stage passes", '(args.staged or os.path.normpath(name) in versioned)', 'os.path.normpath(name) in versioned'),
        ("unreadable becomes clean", 'return 1 if total else (2 if (unreadable or index_failed) else 0)', 'return 1 if total else (2 if index_failed else 0)'),
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
        ("unreadable git index becomes clean", 'return 1 if total else (2 if (unreadable or index_failed) else 0)', 'return 1 if total else (2 if unreadable else 0)'),
        ("settings.local without the slash", 'n.endswith("/" + SETTINGS_LOCAL)', 'n.endswith(SETTINGS_LOCAL)'),
        ("index error becomes empty list", '            return None\n        raw = top.stdout', '            return []\n        raw = top.stdout'),
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
    "ring": dict(file="core/ring.py", suite=["tests/test_ring.py", "tests/test_ring_cache.py", "tests/test_demo.py", "tests/test_people.py"], texts=[
        ("cache ignores the size", 'key = [st.st_size, st.st_mtime_ns]', 'key = [0, st.st_mtime_ns]'),
        ("cache ignores the mtime", 'key = [st.st_size, st.st_mtime_ns]', 'key = [st.st_size, 0]'),
        ("a fresh file is cached", 'if st.st_mtime_ns < time.time_ns() - RACY_NS:', 'if True:'),
        ("the racy window is zero", 'RACY_NS = 2_000_000_000', 'RACY_NS = 0'),
        ("a cache hit does not refresh the entry", 'fresh[rel] = hit\n        return hit[2]', 'return hit[2]'),
        ("the cached targets are not used", 'return hit[2]', 'return link_targets(vault, rel)'),
        ("an old cache version is trusted", 'if data["version"] != CACHE_VERSION or not isinstance(notes, dict):', 'if not isinstance(notes, dict):'),
        ("a cache that is not a map is trusted", ' or not isinstance(notes, dict):', ':'),
        ("a malformed cache entry is trusted", 'if isinstance(v, list) and len(v) == 3 and isinstance(v[2], list)', 'if True'),
        ("a corrupt cache stops the gate", 'except (OSError, ValueError, KeyError, TypeError):', 'except OSError:'),
        ("an unwritable cache stops the gate", 'pass  # read-only .git: the next run just reads the files again', 'raise'),
        ("deleted notes stay in the cache", 'save_cache(cache_file, fresh)\n    return notes, degree', 'save_cache(cache_file, {**cache, **fresh})\n    return notes, degree'),
        ("the stage gate does not use the cache", 'git_cache_file(vault) if stage_only else None', 'None'),
        ("the plain gate uses the cache", 'git_cache_file(vault) if stage_only else None', 'git_cache_file(vault)'),
        ("the cache lives in the vault", 'os.path.join(r.stdout.strip(), "cogiforge-edges.json")', 'os.path.join(str(vault), "cogiforge-edges.json")'),
        ("a known key of another script is rejected", 'if sep and key.strip() in GATE_KEYS and key.strip() != "orphan":\n            continue', 'if False:\n            continue'),
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
        ("people inbox stops being exempt", 'or bool(PEOPLE_INBOX.match(rel))', ''),
        ("people inbox exempt by prefix", r'^people/[^/]+/inbox(/|$)', r'^people/[^/]+/inbox'),
        ("missing gate.txt stops meaning block", 'if not f.exists():\n        return "block"', 'if not f.exists():\n        return "warn"'),
        ("comment-only gate.txt stops meaning block", '    mode = "block"\n    for n, raw', '    mode = "warn"\n    for n, raw'),
        ("warn still blocks", 'if orphans and mode == "warn":', 'if False:'),
        ("warn stops reporting", 'print(f"WARNING — {len(orphans)} note(s) with no inbound', 'print(f"NOTE — {len(orphans)} note(s) with no inbound'),
        ("everything is warn", 'if orphans and mode == "warn":', 'if orphans:'),
        ("unknown value accepted", 'if mode not in ORPHAN_MODES:', 'if False:'),
        ("unknown key accepted", 'if key.strip() != "orphan" or not sep:', 'if False:'),
        ("malformed config is skipped", 'print(f"ERROR: {e}. The gate judged nothing, so the commit is blocked until it is fixed.")\n        return 2', 'print(f"ERROR: {e}.")\n        return 0'),
        ("unreadable gate.txt is skipped", 'except (OSError, UnicodeDecodeError) as e:', 'except OSError as e:'),
        ("inline comment not stripped", 'raw.split("#", 1)[0].strip()', 'raw.strip()'),
        ("--stage ignored in the CLI", 'return gate(args.vault, stage_only=args.stage)', 'return gate(args.vault)'),
    ]),
    "hook": dict(file=".githooks/pre-commit", suite=["tests/test_hook_e2e.py", "tests/test_people.py"], texts=[
        ("the target check does not run", "if git diff --cached --name-only --diff-filter=A | grep -q '^vault/notes/.*\\.md$'; then", 'if false; then'),
        ("target block mode does not block", 'python3 core/target.py --vault vault --staged >"$out" 2>&1\n    rc=$?\n    if [ "$rc" -gt 0 ]; then', 'python3 core/target.py --vault vault --staged >"$out" 2>&1\n    rc=$?\n    if false; then'),
        ("the target warning vanishes", "    if grep '^WARNING' \"$out\" >/dev/null 2>&1; then", '    if false; then'),
        ("the budget check does not run", 'python3 core/budget.py --vault vault --root . --staged >"$out" 2>&1', 'true >"$out" 2>&1'),
        ("the budget does not block", 'sed \'s/^/     /\' "$out" | head -24\n    blocked=1\nfi\nif [ "$rc" -eq 3 ]', 'sed \'s/^/     /\' "$out" | head -24\n    blocked=0\nfi\nif [ "$rc" -eq 3 ]'),
        ("target.py missing passes", 'core/conflicts.py core/target.py core/budget.py core/memory.py; do', 'core/conflicts.py core/budget.py core/memory.py; do'),
        ("budget.py missing passes", 'core/conflicts.py core/target.py core/budget.py core/memory.py; do', 'core/conflicts.py core/target.py core/memory.py; do'),
        ("memory.py missing passes", 'core/conflicts.py core/target.py core/budget.py core/memory.py; do', 'core/conflicts.py core/target.py core/budget.py; do'),
        ("the memory check does not run", 'python3 core/memory.py --vault vault --root . --staged >"$out" 2>&1', 'true >"$out" 2>&1'),
        ("the memory check does not block", "sed 's/^/     /' \"$out\" | head -24\n    blocked=1\nelif", "sed 's/^/     /' \"$out\" | head -24\n    blocked=0\nelif"),
        ("the memory check passes blind on rc 3", 'elif [ "$rc" -eq 3 ]; then\n    echo ""\n    echo "  ⛔ COMMIT BLOCKED — memory gate', 'elif false; then\n    echo ""\n    echo "  ⛔ COMMIT BLOCKED — memory gate'),
        ("the memory rc 3 does not block", "sed 's/^/     /' \"$out\" | head -12\n    blocked=1", "sed 's/^/     /' \"$out\" | head -12\n    blocked=0"),
        ("the memory check ignores rc 2", 'if [ "$rc" -eq 1 ] || [ "$rc" -eq 2 ]; then', 'if [ "$rc" -eq 1 ]; then'),
        ("the memory warnings vanish", "grep -E '^(NOT_VERIFIED|WARNING)' \"$out\" | head -12 | sed 's/^/  /' || true", 'true'),
        ("ring does not run", 'python3 core/ring.py --vault vault --gate --stage', 'true'),
        ("ring looks at the whole vault", '--gate --stage', '--gate'),
        (".md filter vanishes", "grep -q '\\.md$'", "grep -q 'ZZZ'"),
        ("ring does not block", "head -20\n        blocked=1\n    elif", "head -20\n    elif"),
        ("ring warning vanishes", "elif grep -q '^WARNING' \"$out\"; then", "elif false; then"),
        ("leak does not run", 'python3 core/leak.py --staged', 'true'),
        ("leak does not block", "    blocked=1\nelif grep -q 'NOT_VERIFIED'", "elif grep -q 'NOT_VERIFIED'"),
        ("NOT_VERIFIED vanishes", "elif grep -q 'NOT_VERIFIED' \"$out\"; then", "elif false; then"),
        ("leak rename warning vanishes", "grep '^WARNING' \"$out\" | sed 's/^/  /' || true", "true"),
        ("always exits 0", '[ "$blocked" -eq 0 ] || {', 'true || {'),
        ("incomplete installation passes", 'if [ ! -f "$f" ]; then', 'if false; then'),
        ("people guard does not run", 'python3 core/people.py --vault vault --staged', 'true'),
        ("people guard does not block", 'real enforcement is CODEOWNERS."\n    blocked=1', 'real enforcement is CODEOWNERS."'),
        ("people guard ignores rc 1",
         'python3 core/people.py --vault vault --staged >"$out" 2>&1\nrc=$?\nif [ "$rc" -eq 1 ]; then',
         'python3 core/people.py --vault vault --staged >"$out" 2>&1\nrc=$?\nif false; then'),
        ("people could-not-judge passes", 'if [ "$rc" -ge 2 ]; then', 'if false; then'),
    ]),
    "people": dict(file="core/people.py", suite=["tests/test_people.py"], texts=[
        ("solo mode is judged", 'if not roles_file.exists():\n        return 0  # solo mode: silent', 'if False:\n        return 0  # solo mode: silent'),
        ("empty roles becomes OK", 'if not roles:\n        print("NOT_VERIFIED', 'if False:\n        print("NOT_VERIFIED'),
        ("empty roles says OK", 'print("NOT_VERIFIED: roles.txt has no line', 'print("OK: roles.txt has no line'),
        ("unreadable roles passes", 'nothing was judged.")\n        return 3\n    except RolesError', 'nothing was judged.")\n        return 0\n    except RolesError'),
        ("bad roles line is skipped", 'if len(parts) != 3 or parts[1] not in ROLES or "@" not in parts[2]:', 'if False:'),
        ("finding does not fail", 'return 1\n    print(f"OK:', 'return 0\n    print(f"OK:'),
        ("e-mail match is case-sensitive", 'roles.get((email or "").casefold())', 'roles.get(email or "")'),
        ("roles are stored case-sensitive", 'out[parts[2].casefold()] = (parts[0], parts[1])', 'out[parts[2]] = (parts[0], parts[1])'),
        ("another folder of the own handle blocked", 'if m and m.group(1) != me[0]:', 'if m:'),
        ("every folder is free", 'if m and m.group(1) != me[0]:', 'if False:'),
        ("admin is judged by the folder rule", 'if me is None or me[1] == "admin":\n        return []\n    out = []', 'if me is None:\n        return []\n    out = []'),
        ("editing an existing project is blocked", 'if st == "A" and NEW_PROJECT.match(rel)]', 'if NEW_PROJECT.match(rel)]'),
        ("deletions are not judged", '--diff-filter=ACMRD', '--diff-filter=ACMR'),
        ("paths outside the vault are judged", 'if p.startswith(prefix)]', 'if True]'),
        ("roles.txt is open to members", 'ADMIN_ONLY = ("roles.txt", "areas.txt")', 'ADMIN_ONLY = ("areas.txt",)'),
        ("areas.txt is open to members", 'ADMIN_ONLY = ("roles.txt", "areas.txt")', 'ADMIN_ONLY = ("roles.txt",)'),
        ("template is not a folder of someone else", 'PERSON_DIR = re.compile(r"^people/([^/]+)/")', 'PERSON_DIR = re.compile(r"^people/([^_/][^/]*)/")'),
        ("git failure becomes solo", 'print("ERROR: could not read the git stage; nothing was judged.", file=sys.stderr)\n        return 2', 'print("ERROR: could not read the git stage; nothing was judged.", file=sys.stderr)\n        return 0'),
        ("selftest always ok", 'return 1 if failed else 0', 'return 0'),
        ("output echoes a reason-less path", 'for f in found:\n        print(f)', 'for f in found:\n        print("")'),
    ]),
    "install": dict(file="install.sh", suite=["tests/test_hook_e2e.py", "tests/test_people.py"], texts=[
        ("team: bad handle accepted", "LC_ALL=C grep -Eq '^[a-z0-9][a-z0-9_-]*$'", "LC_ALL=C grep -Eq ''"),
        ("team: unknown flag accepted", 'elif [ -n "$1" ]; then', 'elif false; then'),
        ("team: existing roles.txt overwritten", '[ -f vault/roles.txt ] && fail', 'false && fail'),
        ("team: no admin line written", '%s admin %s\\n\' "$TEAM" "$email"', '%s\\n\' "$TEAM"'),
        ("team: folder not created", '[ -e "vault/people/$TEAM" ] || cp -R', 'true || cp -R'),
        ("team: roles.txt not exempt from the leak scan", "printf 'vault/roles.txt\\n' >> .leakignore", "true"),

        ("does not activate hooksPath", 'git config core.hooksPath .githooks || fail', 'true || fail'),
        ("old python passes", '    || fail "Python 3.10 or newer is required; found $(python3 -V 2>&1)."', '    || true'),
        ("broken selftest passes", '    || { python3 core/ring.py --selftest >&2; fail "the ring selftest failed: the gate does not catch an orphan."; }', '    || true'),
        ("outside a git repo passes", "    || fail \"this is not a git repository. Use 'git clone', not the zip, or run 'git init' here.\"", '    || true'),
    ]),
    "private": dict(file="core/private.py", suite=["tests/test_private.py"], texts=[
        ("rules are not derived from the lines", 'return [f"Read({PREFIX}{g})" for g in globs]', 'return ["Read(/vault/people/*/private/**)"]'),
        ("rules are not anchored", 'PREFIX = "/vault/"', 'PREFIX = "vault/"'),
        ("duplicates are added", 'added = [r for r in wanted if r not in deny]', 'added = list(wanted)'),
        ("foreign rules are dropped", 'deny.extend(added)', 'deny[:] = added'),
        ("malformed JSON is overwritten", 'except (OSError, UnicodeDecodeError, ValueError) as e:', 'except (OSError, UnicodeDecodeError) as e:'),
        ("wrong shape is accepted", 'if not isinstance(perms, dict) or not isinstance(perms.get("deny", []), list):', 'if False:'),
        ("dot-dot is accepted", 'if ".." in line.split("/"):', 'if False:'),
        ("leading slash is accepted", 'if line.startswith(("/", "~", "!")) or DRIVE.match(line) or "\\\\" in line:', 'if False:'),
        ("--check never fails", 'return 1 if missing else 0', 'return 0'),
    ]),
    "private-install": dict(file="install.sh", suite=["tests/test_private.py"], texts=[
        ("install does not apply the rules", 'python3 core/private.py --apply >/dev/null || {', 'true || {'),
        ("install ignores a failed apply", 'fail "could not write the read-deny rules', 'true "could not write the read-deny rules'),
    ]),
    "ask": dict(file="tools/ask.py", suite=["tools/test_ask.py"], texts=[
        ("no accent folding", '    return "".join(c for c in folded if not unicodedata.combining(c))', '    return folded'),
        ("path not indexed", 'tokens(c["path"]) * 2 + tokens(c["text"])', 'tokens(c["text"])'),
        ("title and path weigh 1x", 'tokens(c["path"]) * 2', 'tokens(c["path"])'),
        ("big section is not split", 'if cur and len(cur) + len(para) + 2 > MAX_CHARS:', 'if False:'),
        ("parts lose the path", '"path": path, "text": part', '"path": rel, "text": part'),
        ("id carries the path, not the heading", 'f"{rel}#{heading}", "path"', 'f"{rel}#{path}", "path"'),
        ("path separator changes", '" > ".join([title]', '" / ".join([title]'),
        ("sibling headings nest", 'stack = [(lv, n) for lv, n in stack if lv < level]', 'stack = [(lv, n) for lv, n in stack if lv <= level]'),
        ("H4 splits a chunk", 'len(m.group(1)) <= 3', 'len(m.group(1)) <= 6'),
        ("H3 does not split a chunk", 'len(m.group(1)) <= 3', 'len(m.group(1)) <= 2'),
        ("headings inside a fence split chunks", 'm = None if fence else HEADING.match(line)', 'm = HEADING.match(line)'),
        ("headings inside a fence are citable", 'elif not fence and (m := HEADING.match(line)):', 'elif (m := HEADING.match(line)):'),
        ("second H1 nests under the first", 'if level == 1 and first_h1:', 'if level == 1 and False:'),
        ("BM25 becomes a plain count", 'score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(d) / avg))', 'score += tf'),
        ("no length normalisation", '(1 - B + B * len(d) / avg)', '1'),
        ("no idf", 'score += idf * tf * (K1 + 1)', 'score += tf * (K1 + 1)'),
        ("stop words are searched", 'if t not in STOP]', 'if True]'),
        ("ties break by index, not id", 'scored.sort(key=lambda s: (-s[0], chunks[s[1]]["id"], s[1]))', 'scored.sort(key=lambda s: (-s[0], s[1]))'),
        ("ties break backwards", 'scored.sort(key=lambda s: (-s[0], chunks[s[1]]["id"], s[1]))', 'scored.sort(key=lambda s: (-s[0], -s[1]))'),
        ("--top ignored", 'ranked = rank(chunks, a.question)[:a.top]', 'ranked = rank(chunks, a.question)'),
        ("--links does not follow", 'extra = linked_chunks(chunks, results, taken, a.top)', 'extra = []'),
        ("--links does not mark", 'dict(c, score=None, via="link")', 'dict(c, score=None, via=None)'),
        ("--links ignores the room", 'if len(out) >= room:', 'if False:'),
        ("--links ignores the heading", 'if heading and norm(other["id"].split("#", 1)[1]) != heading:', 'if False:'),
        ("--links ignores the target note", 'if i in taken or other["note"] != target:', 'if i in taken:'),
        ("--links repeats a taken chunk", 'if i in taken or other["note"] != target:', 'if other["note"] != target:'),
        ("--links keeps .md in the target", 'target = m.group(1).strip().removesuffix(".md")', 'target = m.group(1).strip()'),
        ("cite approves an invented id", 'if norm(heading) not in found:', 'if False:'),
        ("cite is case/accent-sensitive", 'found = {norm(h) for _, h in', 'found = {h for _, h in'),
        ("cite rejects the file-name heading", ' | {norm(note.stem)}', ''),
        ("cite rejects block refs", 'if not heading or heading.startswith("^"):', 'if not heading:'),
        ("cite approves a missing note", 'or not note.is_file():', 'or False:'),
        ("cite approves a hidden-folder note", 'if any(part.startswith(".") for part in Path(path).parts) or', 'if'),
        ("cite keeps .md in the path", '(m.group(1).strip().removesuffix(".md"), (m.group(2)', '(m.group(1).strip(), (m.group(2)'),
        ("cite counts repeats", 'if (path, heading) in seen:', 'if False:'),
        ("cite accepts an answer without citation", 'if not cites:', 'if False:'),
        ("cite does not fail on a bad citation", 'if bad:\n        return 1', 'if False:\n        return 1'),
        ("empty vault does not exit 3 (search)", 'so nothing was searched")\n        return 3', 'so nothing was searched")\n        return 0'),
        ("empty vault does not exit 3 (cite)", 'so no citation could be checked")\n        return 3', 'so no citation could be checked")\n        return 0'),
        ("unreadable answer does not exit 3", 'could not read the answer ({e.__class__.__name__})")\n        return 3', 'could not read the answer ({e.__class__.__name__})")\n        return 1'),
        ("NOT_VERIFIED becomes OK (search)", 'print("NOT_VERIFIED: the vault has no readable chunks, so nothing', 'print("OK: the vault has no readable chunks, so nothing'),
        ("NOT_VERIFIED becomes OK (cite)", 'print("NOT_VERIFIED: the vault has no readable chunks, so no citation', 'print("OK: the vault has no readable chunks, so no citation'),
        ("unreadable answer says OK", 'print(f"NOT_VERIFIED: could not read the answer', 'print(f"OK: could not read the answer'),
        ("frontmatter is indexed", 'return "\\n".join(lines[i + 1:])', 'return text'),
        ("hidden folders are indexed", 'if any(part.startswith(".") for part in rel_parts):', 'if False:'),
        ("unreadable file aborts instead of being skipped", 'except (OSError, UnicodeDecodeError) as e:\n            skipped', 'except OSError as e:\n            skipped'),
        ("skipped files are silent", 'print(f"skipped {s}", file=sys.stderr)\n    if not chunks:\n        print("NOT_VERIFIED: the vault has no readable chunks, so nothing', 'pass\n    if not chunks:\n        print("NOT_VERIFIED: the vault has no readable chunks, so nothing'),
        ("the consultation is never logged", 'if a.log:\n        log_consultation(', 'if False:\n        log_consultation('),
        ("a failed citation is logged too", '    for b in bad:\n        print("FAIL", b)\n    if bad:\n        return 1', '    for b in bad:\n        print("FAIL", b)\n    if a.log is not None:\n        log_consultation(vault, a.log, sorted({p for p, _ in seen}), a.today)\n    if bad:\n        return 1'),
        ("the cited notes are not deduplicated", 'sorted({p for p, _ in seen})', 'sorted([p for p, _ in seen])'),
        ("the log is overwritten", 'with f.open("a", encoding="utf-8") as fh:', 'with f.open("w", encoding="utf-8") as fh:'),
    ]),
    "conflicts": dict(file="core/conflicts.py", suite=["tests/test_conflicts.py"], texts=[
        ("iCloud placeholder not found", 'if name.endswith(".icloud"):', 'if False:'),
        ("Syncthing conflict not found", 'if SYNCTHING_RE.search(name):', 'if False:'),
        ("conflicted copy not found", 'if COPY_RE.search(name):', 'if False:'),
        ("case conflict not found", 'if CASE_RE.search(name):', 'if False:'),
        ("`name (1)` duplicate not found", 'for rx in (PAREN_RE, SPACE_RE):', 'for rx in (SPACE_RE,):'),
        ("`name 2` duplicate not found", 'for rx in (PAREN_RE, SPACE_RE):', 'for rx in (PAREN_RE,):'),
        ("duplicate without a sibling flagged (false positive)", 'if m and exists(str(p.with_name(m.group("base") + ext))):', 'if m:'),
        ("sibling extension ignored", 'm.group("base") + ext', 'm.group("base")'),
        ("sibling looked up outside the folder", 'str(p.with_name(m.group("base") + ext))', 'm.group("base") + ext'),
        ("staged scans the whole index", 'names = git_list("diff", "--cached", "--name-only", "--diff-filter=ACMR")', 'names = git_list("ls-files")'),
        ("unreadable is not rc 3", 'return 3', 'return 0'),
        ("finding does not fail", 'return 1 if found else 0', 'return 0'),
        ("NOT_VERIFIED becomes OK", 'print(f"NOT_VERIFIED: {len(unreadable)} folder(s)', 'print(f"OK: {len(unreadable)} folder(s)'),
        ("missing path is not rc 2", "nothing was scanned: {', '.join(missing)}\", file=sys.stderr)\n            return 2", "nothing was scanned: {', '.join(missing)}\", file=sys.stderr)\n            return 0"),
    ]),
    "new-project": dict(file="tools/new_project.py", suite=["tools/test_new_project.py"], texts=[
        ("name pattern accepts anything", 'if not NAME_RE.fullmatch(name):', 'if False:'),
        ("existing folder is accepted", 'if (projects / name).exists():', 'if False:'),
        ("index row lands before the table end", 'lines.insert(plan["row_at"] + 1, plan["row"])', 'lines.insert(plan["row_at"], plan["row"])'),
        ("empty target is accepted", 'if not target.strip():', 'if False:'),
        ("placeholder target is accepted", 'elif target.strip().casefold() == EXAMPLE_TARGET:', 'elif False:'),
        ("dry run writes", 'if args.dry_run:', 'if False:'),
        ("failed check still exits 0", '''        return 1
    print("OK: hub, gate and ring pass.")''', '''        return 0
    print("OK: hub, gate and ring pass.")'''),
    ]),
    "new-project-skill": dict(file=".claude/skills/cf-new-project/SKILL.md", suite=["tests/test_new_project_skill.py"], texts=[
        ("skill creates without the yes", '4. **Never create without the "yes".**', '4. **Create when it seems right.**'),
        ("skill lets the target be edited", 'Copy it into `--target` unchanged: no fixing, no\n   shortening, no translating.', 'Copy it into `--target`, tidied up.'),
        ("skill asks everything at once", '1. **One question per message.**', '1. **Ask everything at once.**'),
    ]),
    "new-rule-skill": dict(file=".claude/skills/cf-new-rule/SKILL.md", suite=["tests/test_new_rule_skill.py"], texts=[
        ("skill writes a rule with no dated mistake", '2. **No mistake, no rule.**', '2. **A rule is always welcome.**'),
        ("skill writes the rule before the test", '4. **The test comes before the rule.**', '4. **The rule comes before the test.**'),
        ("skill accepts a single input", '5. **A pair, always.**', '5. **One input is enough.**'),
        ("skill writes outside vault without a yes", '6. **Never write outside `vault/` on your own.**', '6. **Write outside `vault/` freely.**'),
        ("skill lets CLAUDE.md grow without saying", '7. **`CLAUDE.md` stays under 5 KB.**', '7. **`CLAUDE.md` may grow.**'),
        ("skill asks everything at once", '1. **One question per message.**', '1. **Ask everything at once.**'),
    ]),
    "hook-sync": dict(file=".githooks/pre-commit", suite=["tests/test_conflicts.py"], texts=[
        ("sync guard does not run", 'python3 core/conflicts.py --staged', 'true'),
        ("sync guard passes on any rc", 'if [ "$rc" -ne 0 ]; then', 'if false; then'),
        ("sync guard does not teach", 'How to fix: compare', 'Fix: compare'),
        ("sync guard does not block", '    fi\n    blocked=1\nfi\n\n# 5. the target', '    fi\nfi\n\n# 5. the target'),
        ("conflicts.py missing passes", 'core/people.py core/conflicts.py core/target.py', 'core/people.py core/target.py'),
    ]),
    "adopt": dict(file="tools/adopt.py", suite=["tests/test_adopt.py"], texts=[
        ("hook back in the versioned tree", 'HOOK = ".git/hooks/pre-commit"', 'HOOK = ".githooks/pre-commit"'),
        ("old install not unset", '            write_local_config(vault, "core.hooksPath", None)', '            pass'),
        ("FIFO hook is opened", 'if not stat.S_ISREG(st.st_mode):\n        return "other"', 'if False:\n        return "other"'),
        ("global hooksPath ignored", 'outer = outer_hooks_path()', 'outer = ""'),
        ("old .githooks with extra files migrated", 'if legacy_dir.is_symlink() or legacy_state != "ours" or others:', 'if False:'),
        ("foreign pre-commit does not block", 'blocking.append(f"{HOOK} exists and is NOT', '(f"{HOOK} exists and is NOT'),
        ("other hook in .git/hooks passes", '            if not n.endswith(".sample") or kind(g / "hooks" / n, False):', '            if False:'),
        ("a wrong plan sha is accepted", 'if args.confirm.strip().lower() != plan["plan_sha256"]:', 'if False:'),
        ("the file contents are not in the plan sha", 'return {p: file_sha(Path(vault) / p) for p in sorted(paths)}', 'return {p: None for p in sorted(paths)}'),
        ("the config is not in the touched state", 'paths = {".git/config" if o[1].startswith("git config") else o[1] for o in ops}', 'paths = {o[1] for o in ops if not o[1].startswith("git config")}'),
        ("the vault is not in the plan sha", 'blob = json.dumps({"vault": plan["vault"], "ops"', 'blob = json.dumps({"ops"'),
        ("the written content is not in the plan sha", 'ops.append([kind, i["path"], what])', 'ops.append([kind, i["path"], None])'),
        ("the recheck runs but changes are ignored", 'if fresh != plan["state"]:', 'if False:'),
        ("a failed write is not undone", '        rollback(vault, created_files, created_dirs, set_keys)\n        raise', '        raise'),
        ("plain hook text not identical", 'if data == HOOK_TEXT.encode("utf-8"):', 'if False:'),
    ]),
    "hub": dict(file="tools/hub.py", suite=["tools/test_hub.py"], texts=[
        ("the cap is exclusive", 'if len(files) > INLINE_MAX:', 'if len(files) >= INLINE_MAX:'),
        ("the cap is huge", 'INLINE_MAX = 40 ', 'INLINE_MAX = 4000 '),
        ("the overflow list lists itself", ' and p != folder / OVERFLOW\n', '\n'),
        ("a file the user wrote is deleted", 'if have is not None and want is None and OVERFLOW_MARK not in have:', 'if False:'),
        ("--check does not see a stale overflow list", 'if check:\n        return "STALE"\n    if want is None:', 'if False:\n        return "STALE"\n    if want is None:'),
        ("the generated list is never removed", 'path.unlink()', 'pass'),
        ("the overflow list is never written", 'path.write_text(want, encoding="utf-8")', 'pass'),
        ("a dry run writes the overflow list", 'side = None if dry else sync_overflow(folder, vault, check)', 'side = sync_overflow(folder, vault, check)'),
        ("a stale overflow list is not reported", 'if side == "STALE":\n        return "STALE"', 'if False:\n        return "STALE"'),
        ("a hidden folder is listed", 'and not any(part.startswith(".") for part in p.relative_to(folder).parts))', ')'),
        ("only the folders are checked, not the file name", 'for part in p.relative_to(folder).parts', 'for part in p.relative_to(folder).parent.parts'),
        ("a hidden project folder is a project", 'if p.is_dir() and not p.name.startswith(".")', 'if p.is_dir()'),
        ("the root has no pointer to the list", 'lines.append(f"- [[{rel}|all {len(files)} files of this project]]")', 'pass'),
    ]),
    "target": dict(file="core/target.py", suite=["tests/test_target.py"], texts=[
        ("the default mode blocks", 'if not f.exists():\n        return "warn"', 'if not f.exists():\n        return "block"'),
        ("an unknown mode is accepted", 'if mode not in MODES:', 'if False:'),
        ("an edited note is asked too", '"--diff-filter=A"', '"--diff-filter=ACMR"'),
        ("every folder is asked", 'c.startswith("notes/")', 'True'),
        ("block mode does not fail", 'return 1 if mode == "block" else 0', 'return 0'),
        ("block mode says WARNING", 'word = "FAILS" if mode == "block" else "WARNING"', 'word = "WARNING"'),
        ("an empty target counts as declared", 'return bool(str(value).strip()) if value is not None else False', 'return True'),
        ("no git stage becomes OK", 'is not in a repo).")\n        return 3', 'is not in a repo).")\n        return 0'),
        ("a missing vault becomes OK", 'the target check judged nothing.")\n        return 3', 'the target check judged nothing.")\n        return 0'),
        ("a malformed gate.txt passes", 'so the commit is blocked until it is fixed.")\n        return 2', 'so the commit is blocked until it is fixed.")\n        return 0'),
        ("an unknown key in gate.txt is accepted", 'if not sep or key.strip() not in gate.GATE_KEYS:', 'if False:'),
        ("an unreadable gate.txt is ignored", 'except (OSError, UnicodeDecodeError) as e:\n        raise ValueError(f"vault/gate.txt exists but cannot be read ({type(e).__name__})")', 'except (OSError, UnicodeDecodeError) as e:\n        return "warn"'),
        ("no NFC", 'unicodedata.normalize("NFC", c)', 'c'),
        ("the report does not teach", 'How to fix: add', 'Add'),
    ]),
    "budget": dict(file="core/budget.py", suite=["tests/test_budget.py"], texts=[
        ("the every-session ceiling is off", 'if m["always"] > ALWAYS_MAX:', 'if False:'),
        ("the every-session ceiling is exclusive", 'if m["always"] > ALWAYS_MAX:', 'if m["always"] >= ALWAYS_MAX:'),
        ("the open-a-project ceiling is off", 'if m["open"] > OPEN_MAX:', 'if False:'),
        ("the open-a-project ceiling is exclusive", 'if m["open"] > OPEN_MAX:', 'if m["open"] >= OPEN_MAX:'),
        ("the whole diary loads", 'DIARY_READ, TASKS_READ = 3, 5', 'DIARY_READ, TASKS_READ = 300, 5'),
        ("every open task loads", 'DIARY_READ, TASKS_READ = 3, 5', 'DIARY_READ, TASKS_READ = 3, 500'),
        ("the oldest diary entries load", 'reverse=True)[:DIARY_READ]', 'reverse=False)[:DIARY_READ]'),
        ("a done task counts as open", r'(open|in-progress)\s*$", re.M)', r'(open|in-progress|done)\s*$", re.M)'),
        ("skill descriptions are free", 'total += len((m.group(1) if m else "").encode("utf-8"))', 'total += 0'),
        ("the worst project is the first", 'key=lambda p: projects[p]["root"] + projects[p]["tasks"]', 'key=lambda p: 0'),
        ("a project root is not counted", '"root": size(rootfile) or 0', '"root": 0'),
        ("nothing readable is OK", 'return 3\n    over = verdict(m)', 'return 0\n    over = verdict(m)'),
        ("a missing vault is OK", 'so no context was measured.")\n        return 3', 'so no context was measured.")\n        return 0'),
        ("over the ceiling is not rc 1", 'return 1 if over else 0', 'return 0'),
        ("a shrinking commit is blocked", 'if not g or not over:\n            return 0', 'if not over:\n            return 0'),
        ("an unchanged file counts as grown", '(now[r] or 0) > (before[r] or 0)', '(now[r] or 0) >= (before[r] or 0)'),
        ("a skill is not a loaded file when staged", '+ skill_files(root)]', ']'),
        ("no git compare becomes OK", 'is not in a repo).")\n            return 3', 'is not in a repo).")\n            return 0'),
        ("the report does not teach", 'How to fix: shrink', 'Shrink'),
    ]),
    "usage": dict(file="tools/usage.py", suite=["tools/test_usage.py"], texts=[
        ("a project file does not use a note", 'is_output = rel.startswith("projects/") or ', 'is_output = False or '),
        ("an output-type note does not use a note", ' or str(fm.get("type", "")).strip() in OUTPUT_TYPES', ''),
        ("any note uses a note", 'if r and r != rel and r.startswith("notes/") and is_output:', 'if r and r != rel and r.startswith("notes/"):'),
        ("a self link is a use", 'if r and r != rel and r.startswith("notes/")', 'if r and r.startswith("notes/")'),
        ("the ask log is not read", 'cited, bad_log = read_log(vault)', 'cited, bad_log = {}, 0'),
        ("a malformed log line stops the report", 'except (ValueError, KeyError, TypeError):\n            bad += 1', 'except ValueError:\n            bad += 1'),
        ("malformed log lines are not reported", 'if data["bad_log_lines"]:', 'if False:'),
        ("the stale limit is exclusive", 'state = "stale" if age >= days else "idle"', 'state = "stale" if age > days else "idle"'),
        ("an undated note is guessed stale", 'elif age is None:\n            state = "undated"', 'elif age is None:\n            state = "stale"'),
        ("a used note can be stale", 'if rel in used:\n            state = "used"', 'if False:\n            state = "used"'),
        ("no notes becomes a zero report", 'if not data["rows"]:', 'if False:'),
        ("a missing vault is OK", 'so no usage was measured.")\n        return 3', 'so no usage was measured.")\n        return 0'),
        ("the real zero is not explained", 'if not data["outputs"] and not data["asked"]:', 'if False:'),
        ("things outside notes/ are counted", 'subjects = [r for r in md if r.startswith("notes/")]', 'subjects = md'),
        ("idle lists the newest first", '-(r["age"] if r["age"] is not None else -1)', '(r["age"] if r["age"] is not None else -1)'),
        ("idle lists used notes", 'r["state"] in ("stale", "idle", "undated")', 'True'),
        ("idle lists other projects", 'r["project"] == project and', 'True and'),
        ("idle ignores --top", ')[:top]', ')'),
        ("a bad --days is accepted", 'a.days < 1 or ', ''),
    ]),
    "cool": dict(file="tools/cool.py", suite=["tools/test_cool.py"], texts=[
        ("the oldest entries are kept", 'key=lambda k: (rest[k]["date"], k), reverse=True)[:keep]', 'key=lambda k: (rest[k]["date"], k), reverse=False)[:keep]'),
        ("a tie keeps the earlier line", 'key=lambda k: (rest[k]["date"], k), reverse=True)', 'key=lambda k: (rest[k]["date"], -k), reverse=True)'),
        ("a continuation line stays behind", r'elif items and items[-1]["kind"] == "entry" and line.strip() and line[:1] in " \t":', 'elif False:'),
        ("the plan writes", 'if not a.apply:\n        print("Plan only', 'if False:\n        print("Plan only'),
        ("any file can be cooled", 'rel.parts[:1] != ("memory",) or ', ''),
        ("a path can escape", '".." in rel.parts or ', ''),
        ("the archive can be cooled", ' or "archive" in rel.parts', ''),
        ("the old pointer stays", ' and i["kind"] != "pointer"]', ']'),
        ("no pointer is left behind", 'out.insert(at, pointer)', 'pass'),
        ("the pointer is not a full path", 'f"- [[{archive_rel}|{total}', 'f"- [[{path_stem}|{total}'),
        ("the archive is overwritten", 'new_archive = old.rstrip("\\n") + "\\n" + body', 'new_archive = body'),
        ("the archive is not in date order", 'sorted(moved, key=lambda e: e["date"])', 'moved'),
        ("no dated entry is OK", 'if not kept and not moved:\n        print(f"NOT_VERIFIED', 'if False:\n        print(f"NOT_VERIFIED'),
        ("an unreadable file is OK", 'nothing was cooled.")\n        return 3', 'nothing was cooled.")\n        return 0'),
        ("--keep 0 is accepted", 'if a.keep < 1:', 'if False:'),
        ("a superseded entry does not go first", 'return [e for e in entries if superseded(e) or id(e) not in newest]', 'return [e for e in entries if id(e) not in newest and not superseded(e)]'),
        ("a superseded entry counts in --keep", 'rest = [e for e in entries if not superseded(e)]', 'rest = entries'),
        ("superseded is never seen", 'return bool(m) and any(k == "superseded_by" and v', 'return False and any(k == "superseded_by" and v'),
    ]),
    "stale": dict(file="tools/stale.py", suite=["tools/test_stale.py"], texts=[
        ("the threshold is exclusive", 'elif n >= threshold:', 'elif n > threshold:'),
        ("moved becomes dead-path", 'findings.append((at, "moved",', 'findings.append((at, "dead-path",'),
        ("--gate has no effect", 'if a.gate and found:\n        return 1', 'if False and found:\n        return 1'),
        ("superseded is ignored", 'if fields.get("superseded_by"):', 'if False:'),
        ("today is fixed", 'if end and end < today:\n                findings.append((at, "expired"', 'if end and end < date(2026, 1, 1):\n                findings.append((at, "expired"'),
        ("a note stale_after is ignored", 'if end and end < today:\n            findings.append((shown(n, root)', 'if False:\n            findings.append((shown(n, root)'),
        ("a same-name file elsewhere is not looked for", 'found = names.get(Path(c).name.lower(), [])', 'found = []'),
        ("a missing git is OK", 'return r.returncode == 0 and r.stdout.strip() == "true"', 'return True'),
        ("memory files are not listed", 'for f in memory.memory_files(vault):', 'for f in []:'),
        ("a commit on the entry day counts", 'since = (day + timedelta(days=1)).isoformat()', 'since = day.isoformat()'),
        ("not verified is OK", 'return 3 if nv else 0', 'return 0'),
        ("a line suffix is kept", 'p = re.sub(r":\d+(?:-\d+)?$", "", p)\n        if EXT', 'if EXT'),
    ]),
    "recall": dict(file="tools/recall.py", suite=["tools/test_recall.py"], texts=[
        ("the pointer is not required", 'has_pointer(read(vault / "memory" / f"{stem}.md"), stem):', 'True:'),
        ("all becomes any", 'return all(hits) if item.get("all") else any(hits)', 'return any(hits)'),
        ("I don't know counts anywhere", 'return UNKNOWN.match(a) is not None', 'return UNKNOWN.search(a) is not None'),
        ("the positive control is ignored", 'if any(res[i["id"]] != "ok" for i in pos):', 'if False:'),
        ("contamination is off", 'if it["type"] == "recall" and contaminated(it, vault, root):', 'if False:'),
        ("a term matches inside a word", 'return re.search(r"(?<![a-z0-9])" + re.escape(term_norm) + r"(?![a-z0-9])", text_norm) is not None', 'return term_norm in text_norm'),
        ("the ceiling is not checked", 'for over in budget.verdict(m):', 'for over in []:'),
        ("a failed static check still runs the model", 'if problems:\n        print("--run skipped', 'if False:\n        print("--run skipped'),
        ("an invented negative control passes", 'return "ok" if unknown else "wrong"', 'return "ok"'),
        ("the unknown answer is graded by the terms first", '    if unknown:\n        return "unknown"\n', ''),
        ("a missing bank is OK", 'print(f"NOT_VERIFIED: there is no bank at {bank}, so nothing was measured. To create it: {HOW_TO_CREATE}.")\n        return 3', 'return 0'),
        ("a repeated id is accepted", 'if iid in seen:', 'if False:'),
        ("digits before I don't know are stripped", r'''a = re.sub(r"^\d+[.)]\s+", "", a, count=1)''', r'''a = re.sub(r"^[\d.)\-\s]+", "", a)'''),
        ("markdown marks are not stripped", r'a = re.sub(r"^[\s>*_]+", "", norm(answer))', 'a = norm(answer)'),
        ("an answer may start at any number", 'and int(m.group(1)) == nxt + 1:', 'and True:'),
        ("the answer range is not checked", 'if m and nxt < n and', 'if m and'),
        ("a continuation line is dropped", 'elif cur is not None and ln.strip():', 'elif False:'),
        ("a missing answer is graded", 'if a is None:\n            return not_verified(', 'if False:\n            return not_verified('),
        ("no recall asked still verifies", 'if not rec:\n        return not_verified(', 'if False:\n        return not_verified('),
        ("a control in the rules file passes", 'and state == "loaded" and (', 'and state == "loaded" and False and ('),
        ("team memory is not read", 'return sorted((vault / "people").glob("*/memory/*.md"))', 'return []'),
        ("a term echoed by the question is accepted", 'if has_term(q, norm(t)):', 'if False:'),
        ("a short term is accepted", 'if len(norm(t).strip()) < 3:', 'if False:'),
        ("any id is accepted", 'not isinstance(iid, str) or not ID_OK.match(iid)', 'not isinstance(iid, str) or not iid.strip()'),
        ("the command runs in another folder", 'cwd=cwd,', 'cwd=None,'),
        ("output that is not UTF-8 is repaired", 'return out.decode("utf-8")  #', 'return out.decode("utf-8", "replace")  #'),
        ("an unclosed quote is not refused", '({e})", file=sys.stderr)\n            return 2', '({e})", file=sys.stderr)\n            return 0'),
        ("an empty command is not refused", 'if not argv_cmd:', 'if False:'),
        ("the exit code of the command is ignored", 'if proc.returncode != 0:', 'if False:'),
        ("a not-verified run prints a score", "(score not valid)", ""),
        ("a not-verified run logs a score", '"recall_ok": None, "recall_total": None,', '"recall_ok": 0, "recall_total": None,'),
        ("the child gets no group of its own", 'start_new_session=not IS_WINDOWS', 'start_new_session=False'),
        ("a timeout kills only the child", 'os.killpg(proc.pid, signal.SIGKILL)', 'os.kill(proc.pid, signal.SIGKILL)'),
        ("a timeout is not caught", 'except (RuntimeError, OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as e:', 'except (RuntimeError, OSError, UnicodeDecodeError) as e:'),
        ("an undecodable output is not caught", 'except (RuntimeError, OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as e:', 'except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:'),
        ("a pointer with .md is not seen", r'(?:\.md)?[|\]]"', r'[|\]]"'),
        ("a pointer in a comment counts", 'text = re.sub(r"<!--.*?-->", "", text, flags=re.S)', 'text = text'),
        ("a pointer in a code block counts", 'text = re.sub(r"^(```|~~~).*?^\\1[^\\n]*$", "", text, flags=re.S | re.M)', 'text = text'),
        ("an inline code pointer counts", 'return re.sub(r"`[^`\\n]*`", "", text)', 'return text'),
        ("all is judged file by file", 'if found("\\n".join(read(p) for p in budget.loaded_files(vault, root) + team_memory(vault)), item):', 'if any(found(read(p), item) for p in budget.loaded_files(vault, root) + team_memory(vault)):'),
        ("archived items are asked", 'asked = [it for it in items if states.get(it["id"]) != "archived"]', 'asked = items'),
        ("a missing vault is not caught", 'if not vault.is_dir():', 'if False:'),
        ("AGENTS.md is not a rules file", 'RULES_FILES = ("CLAUDE.md", "AGENTS.md")', 'RULES_FILES = ("CLAUDE.md",)'),
        ("vault/CLAUDE.md is not a rules file", '+ "\\n" + read(vault / "CLAUDE.md")', '+ "\\n"'),
        ("only one memory stem is searched", 'for stem in budget.MEMORY:', 'for stem in budget.MEMORY[-1:]:'),
    ]),
    "quote": dict(file="core/quote.py", suite=["tests/test_quote.py", "tests/test_memory.py"], texts=[
        ("every piece is not required (all becomes any)", 'return all(" " + p + " " in hay for p in ps)', 'return any(" " + p + " " in hay for p in ps)'),
        ("the word boundary is removed", '" " + p + " " in hay', 'p in hay'),
        ("nothing measurable becomes True", 'if not ps:\n        return None', 'if not ps:\n        return True'),
        ("nothing measurable becomes False", 'if not ps:\n        return None', 'if not ps:\n        return False'),
        ("a one-word piece is measured", 'MIN_WORDS = 3', 'MIN_WORDS = 1'),
        ("accents are not folded", 'if unicodedata.category(c) != "Mn")', 'if True)'),
        ("case is not folded", r'return re.sub(r"\W+", " ", s).lower().strip()', r'return re.sub(r"\W+", " ", s).strip()'),
        ("punctuation is not folded", r'return re.sub(r"\W+", " ", s)', r'return re.sub(r" +", " ", s)'),
        ("editorial brackets are measured", r'CUT = re.compile(r"\[[^\]]*\]|\.\.\.|…")', r'CUT = re.compile(r"\.\.\.|…")'),
        ("the whole phrase is cut at the boundary", 'return " " + n + " " in " " + norm(text) + " "', 'return n in norm(text)'),
        ("a short whole phrase is measured", 'if len(n.split()) < MIN_WORDS:', 'if False:'),
        ("the ellipsis is measured", r'CUT = re.compile(r"\[[^\]]*\]|\.\.\.|…")', r'CUT = re.compile(r"\[[^\]]*\]")'),
    ]),
    "memory": dict(file="core/memory.py", suite=["tests/test_memory.py"], texts=[
        ("a future date is accepted", 'elif parsed > today + timedelta(days=1):', 'elif False:'),
        ("tomorrow is refused", 'elif parsed > today + timedelta(days=1):', 'elif parsed > today + timedelta(days=0):'),
        ("an impossible date is accepted", 'if parsed is None:', 'if False:'),
        ("a bad date in a final field is accepted", 'if valid_date(v) is None:', 'if False:'),
        ("an unknown final field is accepted", 'any(k not in FIELD_KEYS for k, _ in fields)', 'False'),
        ("an empty where is accepted", 'if not where:', 'if False:'),
        ("a file with no format line is accepted", 'if start is None:\n        fails.append(Failure(rel, "shape"', 'if False:\n        fails.append(Failure(rel, "shape"'),
        ("a title after the format line is free", 'if not line.strip() or POINTER.match(line):', 'if not line.strip() or POINTER.match(line) or line.lstrip().startswith("#"):'),
        ("any line with a pointer link passes", r'\]\]$")', r'\]\].*")'),
        ("any line that starts like a pointer passes", 'POINTER = re.compile(r"^- ', 'POINTER = re.compile(r"^.*'),
        ("the pointer stem is free", 'memory/archive/[A-Za-z0-9._-]+', 'memory/archive/[^\\]]+'),
        ("a CRLF line is refused", 'if line.endswith("\\r"):\n            line = line[:-1]', 'if False:\n            line = line[:-1]'),
        ("an invented phrase with a file source passes", 'if got is False:', 'if False:'),
        ("nothing measurable passes silently", 'if got is None:', 'if False:'),
        ("the phrase is cut in pieces (brackets and ellipsis open an exception)", 'got = quote.found_whole(phrase, text)', 'got = quote.found(phrase, text)'),
        ("a chat source blocks by default", 'modes = {"memory-source": "warn", "memory-reach": "warn"}', 'modes = {"memory-source": "block", "memory-reach": "warn"}'),
        ("a url blocks by default", 'modes = {"memory-source": "warn", "memory-reach": "warn"}', 'modes = {"memory-source": "warn", "memory-reach": "block"}'),
        ("memory-source: block does not block", 'if block:\n            return Failure(at, "source", f\'source "{where}" is not a file', 'if not block:\n            return Failure(at, "source", f\'source "{where}" is not a file'),
        ("memory-source: block does not block a new source", 'if block:\n                return Failure(at, "source", f\'source "{where}" is new', 'if not block:\n                return Failure(at, "source", f\'source "{where}" is new'),
        ("memory-reach: block does not block", 'if modes["memory-reach"] == "block":\n                fails.append(Failure(at, "reach"', 'if modes["memory-reach"] != "block":\n                fails.append(Failure(at, "reach"'),
        ("memory-reach: block does not block the header", 'if modes["memory-reach"] == "block":\n        return Failure(rel, "header"', 'if modes["memory-reach"] != "block":\n        return Failure(rel, "header"'),
        ("reach looks only at entries", 'if REACH.search(line):', 'if REACH.search(line) and ENTRY.match(line):'),
        ("reach lost the domain pattern", r'|\b[a-z0-9-]+\.(?:com|net|org|io|dev|sh|app|xyz|ru|cn|info|me)/', ''),
        ("reach lost git push and --no-verify", r'|\bgit\s+push\b|--no-verify', ''),
        ("a source outside the vault is accepted (disk)", 'if relv is None:\n            return fail("resolves outside vault/")', 'if False:\n            return fail("resolves outside vault/")'),
        ("a source outside the vault is accepted (staged)", 'if vrel and not (frel.casefold() + "/").startswith(vrel.casefold() + "/"):', 'if False:'),
        ("a memory file can be a source (disk)", 'if in_memory_folder(relv.casefold()):\n            return fail', 'if False:\n            return fail'),
        ("a memory file can be a source (staged)", 'if in_memory_folder(relv.casefold()):\n        return fail', 'if False:\n        return fail'),
        ("the memory folder test is case-sensitive (disk)", 'if in_memory_folder(relv.casefold()):\n            return fail', 'if in_memory_folder(relv):\n            return fail'),
        ("the memory folder test is case-sensitive (staged)", 'if in_memory_folder(relv.casefold()):\n        return fail', 'if in_memory_folder(relv):\n        return fail'),
        ("a team memory file can be a source", r'(?:memory|people/[^/]+/memory)(?:/|$)", rv))', r'(?:memory)(?:/|$)", rv))'),
        ("a symlink source is followed (disk)", 'res, vres = Path(os.path.realpath(cand)), Path(os.path.realpath(vault))', 'res, vres = Path(os.path.abspath(cand)), Path(os.path.realpath(vault))'),
        ("the staged source is read from the disk", 'text = reader.head(frel)\n    return verdict(text or "")', 'text = (reader.top / frel).read_text(encoding="utf-8", errors="replace") if (reader.top / frel).is_file() else None\n    return verdict(text or "")'),
        ("a source new in the commit is verified", 'if entry is None:\n        if in_index is not None:', 'if entry is None:\n        if False:'),
        ("a source deleted in the commit is verified", 'if entry is not None and in_index is None:', 'if False:'),
        ("a source swapped for a symlink in the index is verified", 'if in_index == "120000":', 'if False:'),
        ("a source behind a symlink in HEAD is verified", 'if entry[0] == "120000":', 'if False:'),
        ("a folder is read as a source", 'if entry[1] != "blob":', 'if False:'),
        ("a BOM is accepted anywhere", 'if c == BOM and first_line and i == 0:', 'if c == BOM:'),
        ("a BOM is never accepted", 'if c == BOM and first_line and i == 0:', 'if c == BOM and False:'),
        ("an emoji selector is always hidden", 'return not (prev and prev != BLANK and unicodedata.category(prev) in ("So", "Sm", "Po"))', 'return True'),
        ("an emoji selector is always fine", 'return not (prev and prev != BLANK and unicodedata.category(prev) in ("So", "Sm", "Po"))', 'return False'),
        ("a selector after Sm or Po is hidden", 'in ("So", "Sm", "Po"))', 'in ("So",))'),
        ("the Braille blank is a symbol base for a selector", 'return not (prev and prev != BLANK and', 'return not (prev and'),
        ("a keycap is hidden", 'if c == VS16 and prev and prev in "0123456789#*" and nxt == KEYCAP:', 'if False:'),
        ("a ZWJ is always fine", 'return not (_emoji_base(prev) and _emoji_base(nxt))', 'return False'),
        ("a ZWJ is always hidden", 'return not (_emoji_base(prev) and _emoji_base(nxt))', 'return True'),
        ("a ZWJ needs only the previous symbol", 'return not (_emoji_base(prev) and _emoji_base(nxt))', 'return not (_emoji_base(prev))'),
        ("a skin tone is not an emoji base", ' or 0x1F3FB <= ord(c) <= 0x1F3FF)', ')'),
        ("the Braille blank is an emoji base", 'return bool(c) and c != BLANK and', 'return bool(c) and'),
        ("a ZWNJ is always fine", 'return not (prev and nxt and unicodedata.category(prev).startswith("L") and unicodedata.category(nxt).startswith("L"))', 'return False'),
        ("a ZWNJ is always hidden", 'return not (prev and nxt and unicodedata.category(prev).startswith("L") and unicodedata.category(nxt).startswith("L"))', 'return True'),
        ("a tag character is always hidden", 'return not _tag_sequence_ok(line, i)', 'return True'),
        ("a tag character is always fine", 'return not _tag_sequence_ok(line, i)', 'return False'),
        ("any tag text after a flag is fine", 'return line[s - 1:e] in FLAGS', 'return True'),
        ("Scotland is not a flag", '("gbeng", "gbsct", "gbwls")', '("gbeng", "gbwls")'),
        ("a made-up flag name is fine", '("gbeng", "gbsct", "gbwls")', '("gbeng", "gbsct", "gbwls", "push")'),
        ("a submodule in place of a loaded path passes", 'if mode not in REGULAR and (k or protected(p, vault, root)):', 'if mode != "120000" and (k or protected(p, vault, root)):'),
        ("a symlink with mode 100644 rules", 'REGULAR = ("100644", "100755")', 'REGULAR = ("100644", "100755", "120000")'),
        ("an executable memory file is refused", 'REGULAR = ("100644", "100755")', 'REGULAR = ("100644",)'),
        ("a CR is always fine", 'return not (before_nl and i == len(line) - 1)', 'return False'),
        ("a CR is always hidden", 'return not (before_nl and i == len(line) - 1)', 'return True'),
        ("a tab is hidden", 'if c == "\\t":\n        return False', 'if False:\n        return False'),
        ("category Cf is not hidden", 'if cat not in ("Cf", "Co", "Cc") and', 'if cat not in ("Co", "Cc") and'),
        ("category Co is not hidden", 'if cat not in ("Cf", "Co", "Cc") and', 'if cat not in ("Cf", "Cc") and'),
        ("category Cc is not hidden", 'if cat not in ("Cf", "Co", "Cc") and', 'if cat not in ("Cf", "Co") and'),
        ("the extra list is not hidden", 'and not any(lo <= o <= hi for lo, hi in HIDDEN_EXTRA):', ':'),
        ("the line separators and the Braille blank are not hidden", '(0x2028, 0x2029), (0x2800, 0x2800), ', ''),
        ("the variation selectors are not hidden", '(0xFE00, 0xFE0F), ', ''),
        ("the fillers are not hidden", '(0x034F, 0x034F), (0x115F, 0x1160), ', ''),
        ("an unreadable file is a pass", 'fails.append(Failure(r, "unreadable"', 'warns.append(("unreadable",'),
        ("the stage is read from the disk", 'if self.top is not None:\n                rel = self.rel(path)', 'if False:\n                rel = self.rel(path)'),
        ("the staged candidates are empty", 'raw = staged_raw(top)', 'raw = []'),
        ("a changed file type (symlink) is not judged", '--diff-filter=ACMRT', '--diff-filter=ACMR'),
        ("a staged symlink is not a failure", 'if mode not in REGULAR and (k or protected(p, vault, root)):', 'if False:'),
        ("a symlink in place of a parent folder passes", r'r"^(?:$|people$|people/[^/]+$|memory(?:/|$)|people/[^/]+/memory(?:/|$))"', r'r"^(?:$)"'),
        ("a symlinked .claude passes", 'return rr is not None and bool(re.match(r"^\\.claude(?:/|$)", rr.casefold()))', 'return False'),
        ("an unstaged symlinked folder passes", 'if dp.is_symlink() and protected(dp, vault, root):', 'if False:'),
        ("an unstaged symlinked file passes", 'if fp.is_symlink():', 'if False:'),
        ("a symlinked vault passes", 'if Path(os.path.abspath(a.vault)).is_symlink():', 'if False:'),
        ("paths are not casefolded (vault side)", 'rv = rv.casefold() if rv is not None else None', 'rv = rv'),
        ("file names are not casefolded", 'name = Path(p).name.casefold()', 'name = Path(p).name'),
        ("CLAUDE.local.md is not loaded", 'LOADED_NAMES = ("claude.md", "agents.md", "claude.local.md")', 'LOADED_NAMES = ("claude.md", "agents.md")'),
        ("AGENTS.md is not loaded", 'LOADED_NAMES = ("claude.md", "agents.md", "claude.local.md")', 'LOADED_NAMES = ("claude.md", "claude.local.md")'),
        (".claude is not loaded", 'if rr is not None and rr.startswith(".claude/") and rr.endswith(".md"):', 'if False:'),
        ("team memory is not judged (entries)", r'or re.match(r"^people/[^/]+/memory/[^/]+\.md$", rv))', ')'),
        ("memory subfolders are not scanned", r'r"^(?:memory|people/[^/]+/memory)/.+\.md$"', r'r"^(?:memory|people/[^/]+/memory)/[^/]+\.md$"'),
        ("observations.md is judged (rel)", 'if rv.rsplit("/", 1)[-1] == "observations.md":', 'if False:'),
        ("observations.md is judged (glob)", 'p.name.casefold() != "observations.md"', 'True'),
        ("a header change does not warn", 'elif header_of(old) == header_of(text):\n        return None, None', 'elif True:\n        return None, None'),
        ("an unchanged header warns", 'elif header_of(old) == header_of(text):\n        return None, None', 'elif False:\n        return None, None'),
        ("a new file does not warn about its header", 'if old is None:\n        msg = f"{rel}: new memory file', 'if False:\n        msg = f"{rel}: new memory file'),
        ("the format line is not part of the header", 'lines if start is None else lines[:start + 1]', 'lines if start is None else lines[:start]'),
        ("the staged gate.txt is read from the disk", 'blob = reader.git_show(f":{grel}") if grel else None', 'blob = (vault / "gate.txt").read_bytes() if (vault / "gate.txt").is_file() else None'),
        ("an unknown gate.txt key is accepted", 'if not sep or key not in gate.GATE_KEYS:', 'if False:'),
        ("a bad gate.txt value is accepted", 'if modes[key] not in MODES:', 'if False:'),
        ("a failure does not fail", 'return 1 if fails else 0', 'return 0'),
        ("no git stage becomes OK", 'is not in a repo).")\n            return 3', 'is not in a repo).")\n            return 0'),
        ("a malformed gate.txt passes", 'so the commit is blocked until it is fixed.")\n        return 2', 'so the commit is blocked until it is fixed.")\n        return 0'),
    ]),
    "citation": dict(file="tools/citation.py", suite=["tools/test_citation.py"], texts=[
        ("a number matches inside a longer number", r'r"(?<![\d.,])" + re.escape(f) + r"(?!\d|[.,]\d)" + suffix', 're.escape(f) + suffix'),
        ("a percent does not need the sign", 'suffix = PERCENT_WORD if n.endswith("%") else ""', 'suffix = ""'),
        ("comma and dot are different numbers", 'return {base, base.replace(",", "."), base.replace(".", ",")}', 'return {base}'),
        ("one right number is enough", 'if not miss:\n        return VERIFIED', 'if hit:\n        return VERIFIED'),
        ("a date counts as a claim", 'clean = RE_DATE.sub(" ", RE_ANY_URL.sub(" ", context))', 'clean = context'),
        ("a year counts as a claim", r'(?<![\w.,])\d{1,3}(?:[.,]\d+)?%?(?!\d)', r'(?<![\w.,])\d{1,4}(?:[.,]\d+)?%?(?!\d)'),
        ("script text counts as the page", 'if not m.group(1) and name in _END_RAW:', 'if False:'),
        ("a 404 is not broken", 'out.update(state=BROKEN, note=f"does not exist (status {status})")', 'out["note"] = "x"'),
        ("an arXiv id with no entry passes", 'if (total and total.group(1) == "0") or not entry:', 'if False:'),
        ("an arXiv title is not compared", 'if hits >= need:', 'if True:'),
        ("no network approves", 'out["note"] = "no network: the form was read', 'out["state"] = VERIFIED\n        out["note"] = "no network: the form was read'),
        ("no answer is broken", 'if status == 0:\n        out["note"] = "no answer', 'if False:\n        out["note"] = "no answer'),
        ("a 405 is broken", 'out.update(state=PARTIAL, note=f"answered {status} to a GET', 'out.update(state=BROKEN, note=f"answered {status} to a GET'),
        ("a 500 is broken", 'out["note"] = f"answered {status}: the server could not settle it', 'out["state"] = BROKEN; out["note"] = f"answered {status}: the server could not settle it'),
        ("a resolving DOI is verified", 'out.update(state=PARTIAL, note="the DOI resolves;', 'out.update(state=VERIFIED, note="the DOI resolves;'),
        ("a DOI with no handle is not broken", 'elif status in (404, 410):\n            out.update(state=BROKEN, note=f"the DOI', 'elif False:\n            out.update(state=BROKEN, note=f"the DOI'),
        ("no citation at all is clean", 'if NOT_VERIFIED in states or not results:', 'if NOT_VERIFIED in states:'),
        ("partial is rc 0", 'if PARTIAL in states:\n        return 4', 'if PARTIAL in states:\n        return 0'),
        ("broken is not rc 1", 'if BROKEN in states:\n        return 1', 'if False:\n        return 1'),
        ("a broken quote is verified", 'elif any(v is False for v in verdicts):', 'elif False:'),
        ("a link outside the vault is a source", 'c.resolve().relative_to(vroot)', 'c.resolve().relative_to(c.resolve())'),
        ("a short quote is checked", 'QUOTE_MIN_WORDS = 5', 'QUOTE_MIN_WORDS = 1'),
        ("a quote in a fenced block is checked", 'if in_fence:\n            continue', 'if False:\n            continue'),
        ("--quotes is ignored", 'check_quotes(text, path, Path(args.vault)) if args.quotes else check_text', 'check_text'),
        ("a short read passes", 'if expected > 0 and len(raw) != expected:', 'if False:'),
        ("an unreadable file is rc 0", 'could not read {path} ({e})")\n        return 3', 'could not read {path} ({e})")\n        return 0'),
        ("a private address is requested", 'if not allowed_url(url):\n        return REFUSED, ""', 'if False:\n        return REFUSED, ""'),
        ("a redirect is not checked", 'if not allowed_url(newurl):', 'if False:'),
        ("a loopback address counts as public", 'return ip.is_global and not ip.is_multicast', 'return True'),
        ("a name is connected to without checking its address", 'if not public_ip(ip):\n            raise Refused', 'if False:\n            raise Refused'),
        ("IPv6 outside global unicast passes", 'if ip not in _GLOBAL_UNICAST_V6:', 'if False:'),
        ("the run has no wall-clock budget", 'if fetch is not None and time.monotonic() - start > MAX_TOTAL_SECONDS:', 'if False:'),
        ("the fetch has no wall-clock bound", 'worker.join(MAX_SECONDS + TIMEOUT)', 'worker.join()'),
        ("the fetch limit is not applied", 'if fetch is not None and opened >= MAX_FETCHES:', 'if False:'),
        ("a huge file is read", 'if expected > MAX_FILE_BYTES:', 'if False:'),
        ("a dotdot DOI is requested", 'if ".." in item["target"]:', 'if False:'),
        ("control characters reach the output", '"?" if unicodedata.category(c) in', 'c if unicodedata.category(c) in'),
        ("the output is not cleaned", 'shown = [{k: (clean(v) if isinstance(v, str) else v) for k, v in r.items()} for r in results]', 'shown = results'),
    ]),
    "proof": dict(file="core/proof.py", suite=["tests/test_proof.py"], texts=[
        ("a check that touched nothing keeps its return", 'if len(rec) == 0:\n        return Verdict(name, NOT_VERIFIED, [], "touched nothing', 'if False:\n        return Verdict(name, NOT_VERIFIED, [], "touched nothing'),
        ("a null verdict without a reason is accepted", 'if null and self.reason is None:\n            raise ReasonMissing(\n                f"verdict', 'if False:\n            raise ReasonMissing(\n                f"verdict'),
        ("a null verdict can claim single", 'if null and self.reason is Reason.SINGLE:', 'if False:'),
        ("a concluded verdict can carry a null reason", 'elif self.reason is not Reason.SINGLE:\n                raise', 'elif False:\n                raise'),
        ("single with a null value is accepted", 'if self.reason is Reason.SINGLE and self.value is None:', 'if False:'),
        ("a null reason with a value is accepted", 'if self.reason is not Reason.SINGLE and self.value is not None:', 'if False:'),
        ("a string is a reason", 'if not isinstance(self.reason, Reason):', 'if False:'),
        ("a placeholder is a failure", 'return Measure(None, Reason.WRONG_TYPE, f"placeholder', 'return Measure(None, Reason.FAILED, f"placeholder'),
        ("an empty folder is a failure", 'return Measure(None, Reason.NOTHING_TO_MEASURE, f"no {pattern}', 'return Measure(None, Reason.FAILED, f"no {pattern}'),
        ("two candidates pick the first", 'if len(found) > 1:', 'if len(found) > 99:'),
        ("a missing folder is nothing to measure", 'return Measure(None, Reason.FAILED, f"{p} is not a folder")', 'return Measure(None, Reason.NOTHING_TO_MEASURE, f"{p} is not a folder")'),
        ("an exception is a plain failure", 'return Verdict(name, ERROR, rec.touches, f"{type(e).__name__}: {e}", reason=Reason.FAILED)', 'return Verdict(name, FAILED, rec.touches, f"{type(e).__name__}: {e}", reason=Reason.SINGLE)'),
        ("a check that did not conclude is verified", 'if r is None:\n        return Verdict(name, NOT_VERIFIED', 'if r is None:\n        return Verdict(name, VERIFIED'),
        ("a falsy measured value is a failure", 'if r.has_value:\n            return Verdict(name, VERIFIED', 'if r.value:\n            return Verdict(name, VERIFIED'),
        ("the scoreboard forgives NOT_VERIFIED", 'rc = 0 if (n_bad == 0 and n_nv == 0 and n_err == 0) else 1', 'rc = 0 if (n_bad == 0 and n_err == 0) else 1'),
        ("the scoreboard forgives ERROR", 'rc = 0 if (n_bad == 0 and n_nv == 0 and n_err == 0) else 1', 'rc = 0 if (n_bad == 0 and n_nv == 0) else 1'),
        ("a short read passes", 'if len(raw) != expected:', 'if False:'),
        ("a placeholder read passes", 'if expected > 0 and len(raw) == 0:', 'if False:'),
        ("NOT_VERIFIED counts as OK", 'return self.status == VERIFIED', 'return self.status in (VERIFIED, NOT_VERIFIED)'),
        ("the reason is not printed", 'why = f" [{v.reason}]" if v.reason and v.reason is not Reason.SINGLE else ""', 'why = ""'),
    ]),
    "agents_watch": dict(file="tools/agents_watch.py", suite=["tools/test_agents_watch.py"], texts=[
        ("truncated project folder not matched", 'if len(slug) > 200:', 'if False:'),
        ("stderr left unprotected", '    for s in (sys.stdout, sys.stderr):', '    for s in (sys.stdout,):'),
        ("an idle transcript is never stopped", 'r["state"] = RUNNING if r["processes"] else STOPPED', 'r["state"] = RUNNING'),
        ("a recent transcript counts as stopped", 'if idle < minutes:', 'if False:'),
        ("idle CPU counts as alive", 'if p["cpu"] <= CPU_MIN:', 'if False:'),
        ("no process list becomes stopped", 'if ps is None:\n        r["reason"]', 'if False:\n        r["reason"]'),
        ("end_turn is not finished", 'return m.get("stop_reason") == "end_turn"', 'return False'),
        ("SubagentStop is ignored", '== "SubagentStop"', '== "Never"'),
        ("a missing promised file is fine", 'if any(x["verdict"] in ("MISSING", "EMPTY") for x in res):', 'if False:'),
        ("a 0-byte promised file is fine", 'if st.st_size == 0:\n        return "EMPTY"', 'if False:\n        return "EMPTY"'),
        ("a placeholder file is OK", 'if (getattr(st, "st_flags", 0) & DATALESS) or', 'if False and'),
        ("a relative path is checked as absolute", 'if not (c.startswith("/") or c.startswith("~")):', 'if False:'),
        ("a path that is only read counts", 'if not PROMISE.search(seg):', 'if False:'),
        ("an alarm does not fail", 'return 1 if any(r["state"] in (STOPPED, MISSING) for r in rs) else 0', 'return 0'),
        ("nothing readable is OK", 'if not rs or all(r["state"] == NV for r in rs):', 'if False:'),
        ("an unreadable file is not NOT_VERIFIED", 'r = {"agent": aid, "description": "", "state": NV,', 'r = {"agent": aid, "description": "", "state": STOPPED,'),
        ("a missing session is OK", 'print(f"NOT_VERIFIED: {ex}", file=sys.stderr)\n        return 3', 'print(f"NOT_VERIFIED: {ex}", file=sys.stderr)\n        return 0'),
        ("--min 0 is accepted", 'if a.min < 1:', 'if False:'),
    ]),
    "flags": dict(file="tools/flags.py", suite=["tools/test_flags.py"], texts=[
        ("stderr left unprotected", '    for s in (sys.stdout, sys.stderr):', '    for s in (sys.stdout,):'),
        ("a cited flag that does not exist passes", 'res.append(Citation(md.name, line, script, flag, STALE,', 'res.append(Citation(md.name, line, script, flag, OK,'),
        ("a stale flag does not fail", '    if stale:\n        return "\\n".join(out), 1', '    if False:\n        return "\\n".join(out), 1'),
        ("nothing verified becomes OK", '    if not ok:\n        out.append("NOT_VERIFIED:', '    if False:\n        out.append("NOT_VERIFIED:'),
        ("a dead script path is stale", 'NOT_VERIFIED, "the script does not exist (dead path)"', 'STALE, "the script does not exist (dead path)"'),
        ("a dynamic parser counts as complete", '    if a.dynamic:\n        a.verdict, a.reason = NOT_VERIFIED, "failed"', '    if False:\n        a.verdict, a.reason = NOT_VERIFIED, "failed"'),
        ("a flag a dynamic snippet may declare is stale", '        if not a.complete:\n            res.append(Citation(md.name, line, script, flag, NOT_VERIFIED,', '        if False:\n            res.append(Citation(md.name, line, script, flag, NOT_VERIFIED,'),
        ("no parser is read as zero flags", 'elif not has_argparse and not has_argv:', 'elif False:'),
        ("--help is invented with add_help=False", 'add_help = False', 'add_help = True'),
        ("abbreviation is never accepted", 'if len(longer) == 1:', 'if False:'),
        ("any abbreviation is accepted", 'if len(longer) == 1:', 'if len(longer) >= 1:'),
        ("sys.argv comparisons are ignored", '        if isinstance(node, ast.Compare):', '        if False:'),
        ("startswith with a computed prefix is complete", 'if f.attr == "startswith":\n                                dyn(', 'if False:\n                                dyn('),
        ("add_argument(*names) is not dynamic", 'dyn(node.lineno, f"add_argument(*{text_of(arg.value)})")', 'pass'),
        ("an unreadable script is OK", 'a.verdict, a.reason, a.detail = NOT_VERIFIED, "failed", f"could not read or parse', 'a.verdict, a.reason, a.detail = OK, "failed", f"could not read or parse'),
        ("a flag after the first one is dropped", 'out.extend((n, m.group(0), f) for f in found)', 'out.extend((n, m.group(0), f) for f in found[:1])'),
        ("a missing doc is OK", 'print(f"NOT_VERIFIED: {md} does not exist.")\n                return 3', 'print(f"NOT_VERIFIED: {md} does not exist.")\n                return 0'),
    ]),
    "repeat": dict(file="tools/repeat.py", suite=["tools/test_repeat.py"], texts=[
        ("stderr left unprotected", '    for s in (sys.stdout, sys.stderr):', '    for s in (sys.stdout,):'),
        ("a later memory counts as repeated", 'if m["date"] >= c["date"]:', 'if False:'),
        ("a near memory counts as a repeat", 'if (c["date"] - m["date"]).days <= NEAR_DAYS:', 'if False:'),
        ("a loose word is a match", 'if len(common) < MIN_COMMON:', 'if False:'),
        ("every score passes the threshold", 'if s < threshold:', 'if False:'),
        ("the match is not the best older one", '            break  # only the best OLDER memory counts', '            pass'),
        ("accents hide a match", 'unicodedata.normalize("NFD", s)', 's'),
        ("case hides a match", 'if unicodedata.category(c) != "Mn").lower()', 'if unicodedata.category(c) != "Mn")'),
        ("a continuation line is dropped", r'elif out and out[-1] is not None and line.strip() and line[:1] in " \t":', 'elif False:'),
        ("the corrections file is read as memory", 'if f.resolve() != skip:', 'if True:'),
        ("no memory is OK", 'if not memory:\n        print("NOT_VERIFIED', 'if False:\n        print("NOT_VERIFIED'),
        ("no correction is OK", 'if not corrections:\n        print(f"NOT_VERIFIED', 'if False:\n        print(f"NOT_VERIFIED'),
        ("an unreadable file is OK", 'nothing was compared.")\n        return 3', 'nothing was compared.")\n        return 0'),
        ("--gate never fails", 'return 1 if a.gate and r["candidates"] else 0', 'return 0'),
        ("one repeat alone is a candidate", 'if r["n"] == 1 and near.get(k) and k not in candidates]', 'if r["n"] == 1 and k not in candidates]'),
        ("the threshold is not validated", 'if not 0 < a.threshold <= 1:', 'if False:'),
    ]),
    "synth": dict(file="tools/synth.py", suite=["tools/test_synth.py"], texts=[
        ("the seed is ignored", 'rng = random.Random(seed)', 'rng = random.Random(7)'),
        ("a folder with files is overwritten", 'if out.exists() and any(out.iterdir()) and not a.force:', 'if False:'),
        ("links are not preferential", 'j = rng.choice(urn) if urn and rng.random() < 0.6 else rng.randrange(i)', 'j = rng.randrange(i)'),
        ("projects are all the same size", 'self.weights = [1 / (k + 1) ** 0.9 for k in range(self.n_projects)]', 'self.weights = [1 for k in range(self.n_projects)]'),
        ("no note is ever used", 'USED_SHARE = 0.15', 'USED_SHARE = 0.0'),
        ("the project roots carry no list", 'hub.run(v, check=False, dry=False)', 'pass'),
        ("memory does not grow", 'for _ in range(n // 100)]', 'for _ in range(2)]'),
        ("too few notes are accepted", 'if a.notes < 20:', 'if False:'),
    ]),
    "voice_check": dict(file="tools/voice_check.py", suite=["tests/test_voice_check.py"], texts=[
        ("avoid stops counting", 'KINDS = {"never say": "never", "avoid": "avoid"}', 'KINDS = {"never say": "never"}'),
        ("absence becomes OK", 'print("NOT_VERIFIED: no effective rule', 'print("OK: no effective rule'),
        ("no NFKC", 'unicodedata.normalize("NFKC", text).casefold()', 'text.casefold()'),
        ("no word boundary", 'return re.search(r"(?<!\\w)" + re.escape(term) + r"(?!\\w)", line) is not None', 'return term in line'),
        ("code blocks are scanned", 'if fence is None and line.strip():', 'if line.strip():'),
        ("echoes the line", 'print(f"{args.text}:{n}: [{kind}] {term}")',
         'print(f"{args.text}:{n}: [{kind}] {term} {text.splitlines()[n-1]}")'),
    ]),
    "brand_preview": dict(file="tools/brand_preview.py", suite=["tests/test_brand_preview.py"], texts=[
        ("wrong luminance weights", '0.2126 * channel(r) + 0.7152 * channel(g)', '0.7152 * channel(r) + 0.2126 * channel(g)'),
        ("AA threshold too low", 'AA, AAA = 4.5, 7.0', 'AA, AAA = 3.0, 7.0'),
        ("AAA threshold equals AA", 'if ratio >= AAA:', 'if ratio >= AA:'),
        ("invalid hex passes", 'if not isinstance(value, str) or not HEX_RE.match(value):', 'if not isinstance(value, str):'),
        ("no colors becomes OK", '"NOT_VERIFIED: no colors declared', '"OK: no colors declared'),
        ("values are not escaped", 'e = html.escape', 'e = str'),
    ]),
    "skill_spec": dict(file="tests/test_skill_spec.py", suite=["tests/test_skill_spec.py"], texts=[
        ("missing SKILL.md passes", 'return [f"{skill_dir.name}: SKILL.md does not exist"]', 'return []'),
        ("no frontmatter passes", 'return [f"{skill_dir.name}: no frontmatter"]', 'return []'),
        ("missing name passes", 'errors.append("no name")', 'pass'),
        ("name length ignored", 'if not 1 <= len(name) <= MAX_NAME:', 'if False:'),
        ("name charset ignored", 'if not re.fullmatch(r"[a-z0-9-]+", name):', 'if False:'),
        ("edge hyphen allowed", 'if name.startswith("-") or name.endswith("-"):', 'if False:'),
        ("double hyphen allowed", 'if "--" in name:', 'if False:'),
        ("name may differ from the folder", 'if name != skill_dir.name:', 'if False:'),
        ("missing description passes", 'errors.append("no description")', 'pass'),
        ("description cap off by one", 'elif not 1 <= len(desc) <= MAX_DESC:', 'elif not 1 <= len(desc) <= MAX_DESC + 1:'),
        ("quotes counted in the length", 'v = v[1:-1]', 'pass'),
        ("line cap off by one", 'if lines >= MAX_LINES:', 'if lines > MAX_LINES:'),
        ("line cap off by one (lenient)", 'if lines >= MAX_LINES:', 'if lines >= MAX_LINES + 1:'),
        ("empty glob passes", 'assert found, f"no skill found', 'assert True, f"no skill found'),
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


CURRENT = None  # the suite process that is running, so a signal can kill its whole group


def kill_group(proc):
    """Kills the suite and every child it started (a group of its own). Windows has no killpg: only the process."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except OSError:
            pass


def _on_signal(signum, frame):
    if CURRENT is not None:
        kill_group(CURRENT)
    sys.exit(128 + signum)


def install_handlers():
    for name in ("SIGTERM", "SIGHUP", "SIGINT"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _on_signal)


def run_suite(suite):
    global CURRENT
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "pytest", *suite, "-q", "--no-header", "-x",
                             "-p", "no:cacheprovider", "-W", "ignore"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            cwd=ROOT, env=env, start_new_session=True)
    CURRENT = proc
    try:
        out, _ = proc.communicate(timeout=SUITE_TIMEOUT)
    except subprocess.TimeoutExpired:
        kill_group(proc)
        proc.communicate()
        return TIMEOUT_RC, []
    except BaseException:  # KeyboardInterrupt or anything else: never leave the suite running
        kill_group(proc)
        raise
    finally:
        CURRENT = None
    class r:  # noqa: N801  (same shape the lines below read)
        stdout, returncode = out, proc.returncode
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
    install_handlers()
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
                elif rc == TIMEOUT_RC:
                    print(f"  killed (timeout) {name}")
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
