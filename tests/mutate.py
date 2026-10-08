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
        ("a target line in gate.txt is rejected", 'if key.strip() == "target" and sep:\n            continue', 'if False:\n            continue'),
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
        ("the budget does not block", 'sed \'s/^/     /\' "$out" | head -24\n    blocked=1', 'sed \'s/^/     /\' "$out" | head -24\n    blocked=0'),
        ("target.py missing passes", 'core/conflicts.py core/target.py core/budget.py; do', 'core/conflicts.py core/budget.py; do'),
        ("budget.py missing passes", 'core/conflicts.py core/target.py core/budget.py; do', 'core/conflicts.py core/target.py; do'),
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
        ("the consultation is never logged", 'if a.log is not None:', 'if False:'),
        ("a failed citation is logged too", '    for b in bad:\n        print("FAIL", b)\n    if bad:\n        return 1', '    for b in bad:\n        print("FAIL", b)\n    if a.log is not None:\n        log_consultation(vault, a.log, sorted({p for p, _ in seen}), a.today)\n    if bad:\n        return 1'),
        ("the cited notes are not deduplicated", 'sorted({p for p, _ in seen})', 'sorted([p for p, _ in seen])'),
        ("the question is not cut", 'QUESTION_MAX = 200', 'QUESTION_MAX = 20'),
        ("the question is not flattened", '" ".join(question.split())', 'question'),
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
    "hook-sync": dict(file=".githooks/pre-commit", suite=["tests/test_conflicts.py"], texts=[
        ("sync guard does not run", 'python3 core/conflicts.py --staged', 'true'),
        ("sync guard passes on any rc", 'if [ "$rc" -ne 0 ]; then', 'if false; then'),
        ("sync guard does not teach", 'How to fix: compare', 'Fix: compare'),
        ("sync guard does not block", '    fi\n    blocked=1\nfi\n\n# 5. the target', '    fi\nfi\n\n# 5. the target'),
        ("conflicts.py missing passes", 'core/people.py core/conflicts.py core/target.py', 'core/people.py core/target.py'),
    ]),
    "hub": dict(file="tools/hub.py", suite=["tools/test_hub.py"], texts=[
        ("the cap is exclusive", 'if len(files) > INLINE_MAX:', 'if len(files) >= INLINE_MAX:'),
        ("the cap is huge", 'INLINE_MAX = 40 ', 'INLINE_MAX = 4000 '),
        ("the overflow list lists itself", ' and p != folder / OVERFLOW)', ')'),
        ("a file the user wrote is deleted", 'if have is not None and want is None and OVERFLOW_MARK not in have:', 'if False:'),
        ("--check does not see a stale overflow list", 'if check:\n        return "STALE"\n    if want is None:', 'if False:\n        return "STALE"\n    if want is None:'),
        ("the generated list is never removed", 'path.unlink()', 'pass'),
        ("the overflow list is never written", 'path.write_text(want, encoding="utf-8")', 'pass'),
        ("a dry run writes the overflow list", 'side = None if dry else sync_overflow(folder, vault, check)', 'side = sync_overflow(folder, vault, check)'),
        ("a stale overflow list is not reported", 'if side == "STALE":\n        return "STALE"', 'if False:\n        return "STALE"'),
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
        ("the oldest entries are kept", 'key=lambda k: (entries[k]["date"], k), reverse=True)[:keep]', 'key=lambda k: (entries[k]["date"], k), reverse=False)[:keep]'),
        ("a tie keeps the earlier line", 'key=lambda k: (entries[k]["date"], k), reverse=True)', 'key=lambda k: (entries[k]["date"], -k), reverse=True)'),
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
