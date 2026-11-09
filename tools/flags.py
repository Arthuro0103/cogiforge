#!/usr/bin/env python3
"""flags.py: list the CLI flags of a Python script WITHOUT importing or running it, and check that the
command tables in a Markdown file cite only flags the scripts really have. Stdlib only.

    python3 tools/flags.py <script.py>            list the flags and where each one is declared
    python3 tools/flags.py --tables <file.md>     check every flag cited next to a core/, tools/ or tests/ script
    python3 tools/flags.py --tables               same, for CLAUDE.md and AGENTS.md at the repo root
    python3 tools/flags.py --selftest

Running `--help` on a script can execute it (and write files). Here only `ast.parse` reads the TEXT: no line
of the target runs, no import happens, nothing is written. Docs that name a flag that does not exist fail.

The list never pretends to be complete. A dynamic parser (a flag built in a loop, an f-string, a variable,
`add_argument(*names)`, `getattr`) returns the flags found PLUS NOT_VERIFIED with the line of the snippet.
A script with neither argparse nor `sys.argv` is NOT_VERIFIED too ("nothing to measure" is not "0 flags").
A table check that verified no flag at all (no command found, or every script missing) is NOT_VERIFIED, never OK.
rc: 0 every cited flag exists · 1 STALE (a cited flag does not exist) · 2 usage · 3 NOT_VERIFIED
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK = "OK"
STALE = "STALE"
NOT_VERIFIED = "NOT_VERIFIED"
DEFAULT_DOCS = ("CLAUDE.md", "AGENTS.md")

# a receiver that "looks like" argv: `sys.argv`, `argv`, `args`, `av`, `opt`, `flag`, `a`
ARGV_LIKE = re.compile(r"\bargv\b|\bargs?\b|\bav\b|\bopts?\b|\bflag\b|^a$")
FLAG_NAME = re.compile(r"^-{1,2}[A-Za-z0-9]")
SCRIPT_REF = re.compile(r"(?:core|tools|tests)/[\w.-]+\.py")
FLAG_TOKEN = re.compile(r"^(--?[A-Za-z][\w-]*)(?:=.*)?$")


@dataclass
class Flag:
    name: str
    origin: str  # "argparse" | "sys.argv"
    line: int  # 0 = implicit (argparse adds -h/--help)


@dataclass
class Analysis:
    path: str
    verdict: str = OK
    reason: str = ""
    flags: list[Flag] = field(default_factory=list)
    dynamic: list[tuple[int, str]] = field(default_factory=list)
    detail: str = ""
    allow_abbrev: bool = True

    @property
    def complete(self) -> bool:
        return self.verdict == OK

    def names(self) -> dict[str, Flag]:
        return {f.name: f for f in self.flags}


def text_of(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001  (a node we cannot print is shown as empty, never fatal)
        return ""


def const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def is_flag(s: str | None) -> bool:
    return bool(s) and FLAG_NAME.match(s) is not None


def analyze(path: str | Path) -> Analysis:
    """Read the flags of `path` from the AST of its text alone."""
    p = Path(path)
    a = Analysis(str(p))
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(p))
    except (OSError, SyntaxError, ValueError) as e:
        a.verdict, a.reason, a.detail = NOT_VERIFIED, "failed", f"could not read or parse: {e}"
        return a

    has_argparse = has_argv = False
    add_help = True

    def found(name: str, origin: str, line: int) -> None:
        a.flags.append(Flag(name, origin, line))

    def dyn(line: int, why: str) -> None:
        a.dynamic.append((line, why))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "argv" and isinstance(node.value, ast.Name) and node.value.id == "sys":
            has_argv = True
        if isinstance(node, ast.ImportFrom) and node.module == "sys" and any(n.name == "argv" for n in node.names):
            has_argv = True

        if isinstance(node, ast.Call):
            f = node.func
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if fname == "ArgumentParser":
                has_argparse = True
                for kw in node.keywords:
                    if kw.arg == "add_help" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        add_help = False
                    if kw.arg == "allow_abbrev" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        a.allow_abbrev = False
            if isinstance(f, ast.Attribute) and f.attr == "add_argument":
                has_argparse = True
                for arg in node.args:
                    if isinstance(arg, ast.Starred):
                        dyn(node.lineno, f"add_argument(*{text_of(arg.value)})")
                        continue
                    s = const_str(arg)
                    if s is None:
                        dyn(node.lineno, f"add_argument({text_of(arg)}): the name is not a literal")
                    elif is_flag(s):
                        found(s, "argparse", node.lineno)
                for kw in node.keywords:
                    if kw.arg is None:
                        dyn(node.lineno, f"add_argument(**{text_of(kw.value)})")
            if isinstance(f, ast.Name) and f.id == "getattr" and len(node.args) >= 2:
                target = const_str(node.args[1])
                if target == "add_argument" or (target is None and re.search(r"pars|^p$|^ap$", text_of(node.args[0]))):
                    has_argparse = True
                    dyn(node.lineno, f"getattr({text_of(node.args[0])}, ...) may register a flag")
            if isinstance(f, ast.Attribute) and f.attr in ("startswith", "index", "count", "remove") and ARGV_LIKE.search(text_of(f.value)):
                for arg in node.args[:1]:
                    cands = arg.elts if isinstance(arg, (ast.Tuple, ast.List, ast.Set)) else [arg]
                    for c in cands:
                        s = const_str(c)
                        if s is None:
                            if f.attr == "startswith":
                                dyn(node.lineno, f"{text_of(f.value)}.startswith({text_of(c)}): computed prefix")
                        elif is_flag(s):
                            found(s.rstrip("="), "sys.argv", node.lineno)

        if isinstance(node, ast.Compare):  # '--x' in argv / argv[1] == '--x'
            sides = [node.left, *node.comparators]
            consts: list[str] = []
            for side in sides:
                if isinstance(side, (ast.Tuple, ast.List, ast.Set)):
                    consts += [c for c in (const_str(e) for e in side.elts) if c]
                elif const_str(side):
                    consts.append(const_str(side))
            flagish = [c for c in consts if is_flag(c)]
            if flagish:
                others = [s for s in sides if const_str(s) is None and not isinstance(s, (ast.Tuple, ast.List, ast.Set))]
                if any(ARGV_LIKE.search(text_of(o)) for o in others):
                    for c in flagish:
                        found(c, "sys.argv", node.lineno)

    if has_argparse and add_help:
        for implicit in ("--help", "-h"):
            if not any(f.name == implicit for f in a.flags):
                a.flags.append(Flag(implicit, "argparse", 0))

    seen: set[tuple[str, str]] = set()
    unique: list[Flag] = []
    for f in a.flags:
        if (f.name, f.origin) not in seen:
            seen.add((f.name, f.origin))
            unique.append(f)
    a.flags = unique

    if a.dynamic:
        a.verdict, a.reason = NOT_VERIFIED, "failed"
        a.detail = "dynamic parser: the list of flags is INCOMPLETE"
    elif not has_argparse and not has_argv:
        a.verdict, a.reason = NOT_VERIFIED, "nothing_to_measure"
        a.detail = "no argparse and no sys.argv: nothing to measure (this is NOT '0 flags')"
    elif not has_argparse and not a.flags:
        a.verdict, a.reason = NOT_VERIFIED, "failed"
        a.detail = "uses sys.argv but no known flag pattern was recognised: the list is INCOMPLETE"
    return a


def render(a: Analysis) -> str:
    out = [f"{a.path}: {a.verdict}" + (f" [reason: {a.reason}]" if a.reason else "")]
    for f in sorted(a.flags, key=lambda x: (x.line == 0, x.line, x.name)):
        out.append(f"  {f.name:<24} {f.origin:<9} {'L' + str(f.line) if f.line else 'implicit'}")
    if not a.flags:
        out.append("  (no flag found)" + ("" if a.complete else " - does NOT mean 'no flags'"))
    if a.dynamic:
        out.append("  INCOMPLETE LIST - dynamic snippets that may register more flags:")
        out += [f"    L{line}: {why}" for line, why in a.dynamic]
    elif not a.complete:
        out.append(f"  {a.detail}")
    return "\n".join(out)


# ----------------------------------------------------------------- --tables

@dataclass
class Citation:
    doc: str
    line: int
    script: str
    flag: str
    status: str
    detail: str = ""


def flags_in(segment: str) -> list[str]:
    found: list[str] = []
    for tok in segment.replace("`", " ").split():
        m = FLAG_TOKEN.match(tok.strip(",.;:)(\"'[]"))
        if m:
            found.append(m.group(1))
    return found


def extract(md: Path) -> list[tuple[int, str, str | None]]:
    """(line, script relative to the repo root, flag or None). Reads text; writes nothing."""
    out: list[tuple[int, str, str | None]] = []
    for n, line in enumerate(md.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        hits = list(SCRIPT_REF.finditer(line))
        for i, m in enumerate(hits):
            end = len(line)
            for sep in ("`", "|"):
                j = line.find(sep, m.end())
                if j != -1:
                    end = min(end, j)
            if i + 1 < len(hits):
                end = min(end, hits[i + 1].start())
            found = flags_in(line[m.end():end])
            if found:
                out.extend((n, m.group(0), f) for f in found)
            else:
                out.append((n, m.group(0), None))
    return out


def check_doc(md: Path, base: Path) -> list[Citation]:
    cache: dict[str, Analysis | None] = {}
    res: list[Citation] = []
    for line, script, flag in extract(md):
        if script not in cache:
            target = base / script
            cache[script] = analyze(target) if target.is_file() else None
        a = cache[script]
        if a is None:
            res.append(Citation(md.name, line, script, flag or "", NOT_VERIFIED, "the script does not exist (dead path)"))
            continue
        if flag is None:
            continue
        names = a.names()
        if flag in names:
            res.append(Citation(md.name, line, script, flag, OK, f"declared by {names[flag].origin}"))
            continue
        if a.allow_abbrev and flag.startswith("--") and any(f.origin == "argparse" for f in a.flags):
            longer = [n for n, f in names.items() if f.origin == "argparse" and n.startswith(flag) and n != flag]
            if len(longer) == 1:
                res.append(Citation(md.name, line, script, flag, OK, f"abbreviation of {longer[0]} (argparse)"))
                continue
        if not a.complete:
            res.append(Citation(md.name, line, script, flag, NOT_VERIFIED,
                                f"not found, but the script's list is INCOMPLETE ({a.reason}: {a.detail})"))
        else:
            res.append(Citation(md.name, line, script, flag, STALE, "the flag does not exist in the script"))
    return res


def report(cits: list[Citation]) -> tuple[str, int]:
    ok = [c for c in cits if c.status == OK]
    stale = [c for c in cits if c.status == STALE]
    nv = [c for c in cits if c.status == NOT_VERIFIED]
    out = [f"{len(cits)} citations: {len(ok)} {OK}, {len(stale)} {STALE}, {len(nv)} {NOT_VERIFIED}"]
    for c in cits:
        out.append(f"  {c.status:<13} {c.doc}:{c.line}  {c.script} {c.flag}".rstrip() + f"  - {c.detail}")
    if stale:
        out.append("STALE:")
        out += [f"  {c.doc}:{c.line}  {c.script} {c.flag}" for c in stale]
    if stale:
        return "\n".join(out), 1
    if not ok:
        out.append("NOT_VERIFIED: no cited flag was checked against a script, so nothing was verified (this is not OK).")
        return "\n".join(out), 3
    return "\n".join(out), (3 if nv else 0)


# ----------------------------------------------------------------- CLI

def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        (t / "a.py").write_text("import argparse\np=argparse.ArgumentParser()\np.add_argument('--x')\n", encoding="utf-8")
        (t / "b.py").write_text("print('hi')\n", encoding="utf-8")
        (t / "c.py").write_text("import argparse\np=argparse.ArgumentParser()\nfor f in ['--a']:\n    p.add_argument(f)\n", encoding="utf-8")
        (t / "d.py").write_text("import sys\nif '--only' in sys.argv: pass\n", encoding="utf-8")
        a, b, c, dd = (analyze(t / n) for n in ("a.py", "b.py", "c.py", "d.py"))
        good = (
            a.complete and "--x" in a.names()
            and b.reason == "nothing_to_measure"
            and c.reason == "failed" and bool(c.dynamic)
            and dd.names()["--only"].origin == "sys.argv"
        )
    print("selftest:", "OK" if good else "FAILED")
    return 0 if good else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("script", nargs="?", help="a Python script to list the flags of")
    ap.add_argument("--tables", nargs="*", metavar="FILE.md", help="check the command tables of these files (default: CLAUDE.md and AGENTS.md)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.tables is not None:
        if a.script:
            print("usage: give either a script or --tables, not both", file=sys.stderr)
            return 2
        docs = [Path(x) for x in a.tables] or [ROOT / n for n in DEFAULT_DOCS]
        cits: list[Citation] = []
        for md in docs:
            if not md.is_file():
                print(f"NOT_VERIFIED: {md} does not exist.")
                return 3
            cits += check_doc(md, ROOT if md.resolve().parent == ROOT else md.resolve().parent)
        text, rc = report(cits)
        print(text)
        return rc
    if not a.script:
        ap.print_usage(sys.stderr)
        return 2
    an = analyze(a.script)
    print(render(an))
    return 0 if an.complete else 3


if __name__ == "__main__":
    sys.exit(main())
