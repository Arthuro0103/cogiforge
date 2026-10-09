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
        ("echoes the data", 'print(f"{shown(name)}:{n}: {kind}")', 'print(f"{shown(name)}:{n}: {kind} {text.splitlines()[n-1]}")'),
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
    "ring": dict(file="core/ring.py", suite=["tests/test_ring.py", "tests/test_demo.py", "tests/test_people.py"], texts=[
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
    "hook-sync": dict(file=".githooks/pre-commit", suite=["tests/test_conflicts.py"], texts=[
        ("sync guard does not run", 'python3 core/conflicts.py --staged', 'true'),
        ("sync guard passes on any rc", 'if [ "$rc" -ne 0 ]; then', 'if false; then'),
        ("sync guard does not teach", 'How to fix: compare', 'Fix: compare'),
        ("sync guard does not block", '    fi\n    blocked=1\nfi\n\n[ "$blocked"', '    fi\nfi\n\n[ "$blocked"'),
        ("conflicts.py missing passes", 'core/people.py core/conflicts.py; do', 'core/people.py; do'),
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
