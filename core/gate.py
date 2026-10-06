#!/usr/bin/env python3
"""gate.py: turns a written rule into a rule that runs. Stdlib only.

    gate.py [--vault vault] [--json] [--check NAME ...] [FILE.md ...]

The 5 checks:
  frontmatter   the block between `---` parses (own parser, subset below)
  area          `area:` is in the configured list and matches the folder `notes/<folder>/`
  dead-link     every [[wikilink]] resolves (root > relative to the note > name in any folder)
  broken-link   `[[` opens and closes on the SAME line (Obsidian does not resolve a link split in two)
  dead-target   `target:` in the frontmatter points to something that exists

Code (fenced block and `inline`) does not count as a link. rc: 0 clean · 1 fails · 2 usage · 3 could not read.

Areas: `<vault>/areas.txt`, one per line, `area` (the folder has the same name) or `folder: area`.
Without the file the 3 examples apply (learning, technology, life). Only applies inside `notes/`.

YAML SUBSET accepted in the frontmatter (anything outside it fails, instead of guessing):
  key: value              plain value, 'single quotes' or "double quotes" (a plain value
                          cannot contain `: ` or end in `:`; use quotes)
  key:                    empty, or followed by `  - item` lines (list)
  key: [a, "b c"]         list on a single line
  # comment               whole line or ` #` at the end of a plain value
Not accepted: nested map, `|` and `>` (block text), anchors `&`/`*`, `!` tags, a tab
in the indentation, frontmatter that opens with `---` and never closes.
"""
import argparse
import json
import os
import re
import sys
from collections import namedtuple
from pathlib import Path

Failure = namedtuple("Failure", "file check msg")

CHECKS = [
    ("frontmatter", "frontmatter parses"),
    ("area", "area: configured and matching the folder"),
    ("dead-link", "every wikilink resolves"),
    ("broken-link", "`[[` opens and closes on the same line"),
    ("dead-target", "target: points to something that exists"),
]
DEFAULT_AREAS = {"learning": "learning", "technology": "technology", "life": "life"}
IGNORE_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
EXTS = (".md", ".canvas", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".txt", ".json",
        ".excalidraw", ".mp4", ".mp3")

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE = re.compile(r"`[^`\n]*`")
WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")


class FMError(Exception):
    pass


def mask(text):
    """Blanks fenced blocks and `inline code`, keeping the line count."""
    out, fence = [], None
    for line in text.split("\n"):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = (m.group(1)[0], len(m.group(1)))
                out.append("")
            else:
                out.append(INLINE.sub(lambda x: " " * len(x.group(0)), line))
        else:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and line.strip() == m.group(1):
                fence = None
            out.append("")
    return "\n".join(out)


def link_target(raw):
    target = raw.replace("\\|", "|").split("|", 1)[0]
    return re.split(r"[#^]", target, maxsplit=1)[0].strip()


def wikilinks(masked_text):
    """[(target, line)] — an anchor to the file itself ([[#x]]) is left out."""
    return [(link_target(m.group(2)), masked_text.count("\n", 0, m.start()) + 1)
            for m in WIKILINK.finditer(masked_text) if link_target(m.group(2))]


# ---- frontmatter: minimal parser ----------------------------------------------

def scalar(v):
    v = v.strip()
    if v[:1] in "\"'":
        if len(v) < 2 or v[-1] != v[0]:
            raise FMError("unclosed quote")
        return v[1:-1]
    if v[:1] == "[":
        if not v.endswith("]"):
            raise FMError("unclosed inline list")
        items = re.findall(r"\"[^\"]*\"|'[^']*'|[^,]+", v[1:-1])
        return [scalar(i) for i in items if i.strip()]
    if v[:1] in "{|>&*!%@`":
        raise FMError(f"`{v[0]}` is outside the accepted subset")
    v = re.sub(r"\s+#.*$", "", v)
    if ": " in v or v.endswith(":"):
        raise FMError("colon without quotes in the value")
    return v


def parse_fm(lines):
    """(dict, None) or (partial, (line, reason)). The line counts from the opening `---`."""
    d, last = {}, None
    for n, raw in enumerate(lines, start=2):
        s = raw.rstrip()
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        try:
            if "\t" in s[:len(s) - len(s.lstrip())]:
                raise FMError("tab in the indentation")
            item = re.match(r"^\s*-\s+(.+)$", s)
            if s[0] in " -":
                if not item or last is None:
                    raise FMError("indentation outside the subset (nested map?)")
                if d[last] is None:
                    d[last] = []
                if not isinstance(d[last], list):
                    raise FMError("list item after a value that is not a list")
                d[last].append(scalar(item.group(1)))
                continue
            m = re.match(r"^([\w-]+)\s*:(?:\s+(.*))?$", s)
            if not m:
                raise FMError(f"line without 'key: value': {s.strip()[:40]!r}")
            last = m.group(1)
            d[last] = scalar(m.group(2)) if m.group(2) is not None and m.group(2).strip() else None
        except FMError as e:
            return d, (n, str(e))
    return d, None


def split_frontmatter(lines):
    """(block lines | None, error | None)."""
    if not lines or lines[0].strip() != "---":
        return None, None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return lines[1:i], None
    return None, (1, "opens with --- and never closes")


# ---- index and note -----------------------------------------------------------

class Index:
    def __init__(self, root, areas=None):
        self.root = Path(root)
        self.paths, self.names = {}, {}   # relpath lower -> relpath ; filename lower -> [relpath]
        for dirpath, dirs, names in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)
            for fn in sorted(names):
                if fn.startswith("."):
                    continue
                rel = (Path(dirpath) / fn).relative_to(self.root).as_posix()
                self.paths[rel.lower()] = rel
                self.names.setdefault(fn.lower(), []).append(rel)
        self.areas = areas if areas is not None else read_areas(self.root)

    def find(self, target, origin):
        """relpath of the file the link resolves to, or None.
        Layers: root > relative to the note > (with slash) path suffix | (no slash) name in any folder."""
        target = target.strip().replace("\\", "/")
        if not target:
            return None
        has_ext = target.lower().endswith(EXTS)
        cands = [target] if has_ext else [target, target + ".md"]
        for c in cands:
            if c.lstrip("/").lower() in self.paths:
                return self.paths[c.lstrip("/").lower()]
        base = os.path.dirname(origin)
        for c in cands:
            r = os.path.normpath(os.path.join(base, c)).replace("\\", "/")
            if r.lower() in self.paths:
                return self.paths[r.lower()]
        if "/" in target:  # with a path: match by path suffix, like Obsidian; never by name alone
            for c in cands:
                for lower, rel in self.paths.items():
                    if lower.endswith("/" + c.lower()):
                        return rel
            return None
        n = target.lower() if has_ext else target.lower() + ".md"
        if n in self.names:
            return self.names[n][0]  # the note in the same folder was already found in the relative layer
        return None


def read_areas(root):
    """{folder: area}. `areas.txt` at the vault root, or the 3 examples."""
    f = Path(root) / "areas.txt"
    if not f.is_file():
        return dict(DEFAULT_AREAS)
    areas = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            folder, _, area = line.partition(":")
            areas[folder.strip()] = (area or folder).strip()
    return areas


class Note:
    def __init__(self, vault, path):
        self.rel = Path(path).relative_to(vault).as_posix()
        self.path = Path(path)
        self.text = Path(path).read_bytes().decode("utf-8")  # UnicodeDecodeError -> unreadable (see audit)
        lines = self.text.split("\n")
        block, self.fm_error = split_frontmatter(lines)
        self.fm = {}
        if block is not None:
            self.fm, self.fm_error = parse_fm(block)
        self.no_code = mask(self.text)


# ---- the 5 checks -------------------------------------------------------------

PLUGIN_FOLDERS = ("tasks",)  # the YAML here belongs to TaskNotes (e.g. timeEntries, a list of maps), not to the subset


def chk_frontmatter(n, idx):
    if not n.fm_error or Path(n.rel).parts[0] in PLUGIN_FOLDERS:
        return []
    return [Failure(n.rel, "frontmatter", f"yaml outside the subset: {n.fm_error[1]} (line {n.fm_error[0]})")]


def chk_area(n, idx):
    parts = Path(n.rel).parts
    if parts[0] != "notes":
        return []
    areas = idx.areas
    if len(parts) < 3:
        return [Failure(n.rel, "area", f"note loose in the root of notes/: move it to notes/<folder>/ "
                                       f"(folders: {', '.join(sorted(areas))})")]
    if n.fm_error:
        return []  # already failed in frontmatter; do not count twice
    folder, area = parts[1], n.fm.get("area")
    expected = areas.get(folder)
    if expected is None:
        return [Failure(n.rel, "area", f"the folder '{folder}' belongs to no configured area")]
    if area is None or not str(area).strip():
        return [Failure(n.rel, "area", f"missing area: field (the folder '{folder}' asks for '{expected}')")]
    area = str(area).strip()
    if area not in areas.values():
        return [Failure(n.rel, "area", f"area: '{area}' is not in the configured list ({', '.join(sorted(set(areas.values())))})")]
    if area != expected:
        area_folder = next(p for p, a in areas.items() if a == area)
        return [Failure(n.rel, "area", f"area: '{area}' lives in notes/{area_folder}/, but the file is in notes/{folder}/")]
    return []


def chk_dead_link(n, idx):
    return [Failure(n.rel, "dead-link", f"[[{target}]] does not resolve (line {ln})")
            for target, ln in wikilinks(n.no_code) if idx.find(target, n.rel) is None]


def chk_broken_link(n, idx):
    out = []
    for i, line in enumerate(n.no_code.split("\n"), 1):
        rest = re.sub(r"\[\[[^\]\n]*\]\]", "", line)
        if "[[" in rest:
            out.append(Failure(n.rel, "broken-link", f"`{rest[rest.index('[['):][:40].strip()}` does not close on line {i}"))
    return out


def chk_target(n, idx):
    target = n.fm.get("target")
    if target is None:
        return []
    out = []
    for a in target if isinstance(target, list) else [target]:
        a = str(a).strip().strip("[]").strip()
        if not a or a.lower() == "none":
            continue
        # disk first (covers a directory and an absolute path); a bare name without a slash counts as a note name
        cands = [idx.root / a, idx.root / (a + ".md")]  # pathlib: `root / "/abs"` is already "/abs"
        if any(c.exists() for c in cands) or ("/" not in a and idx.find(a, n.rel) is not None):
            continue
        out.append(Failure(n.rel, "dead-target", f"target: '{a}' does not exist on disk"))
    return out


ORDER = [chk_frontmatter, chk_area, chk_dead_link, chk_broken_link, chk_target]


# ---- scan ---------------------------------------------------------------------

def collect(vault, targets=None):
    found = []
    for base in targets or [vault]:
        base = Path(base)
        if base.is_file():
            found.append(base)
            continue
        for dirpath, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)
            found += [Path(dirpath) / f for f in sorted(names) if f.endswith(".md") and not f.startswith(".")]
    return found


def audit(vault, files=None, areas=None, checks=None):
    """(.md files scanned, [Failure])."""
    vault = Path(vault)
    idx = Index(vault, areas)
    everything = collect(vault, files)
    failures = []
    for p in everything:
        try:
            n = Note(vault, p)
        except (OSError, UnicodeDecodeError) as e:
            failures.append(Failure(Path(p).relative_to(vault).as_posix(), "UNREADABLE", f"{type(e).__name__}"))
            continue
        for fn in ORDER:
            failures += [f for f in fn(n, idx) if not checks or f.check in checks]
    return everything, failures


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="append", help="run only this check (repeatable)")
    args = ap.parse_args(argv)
    vault = Path(args.vault)
    names = {c for c, _ in CHECKS}
    if not vault.is_dir() or (args.check and set(args.check) - names):
        print(f"ERROR: vault does not exist ({vault}) or unknown check (valid: {', '.join(sorted(names))})", file=sys.stderr)
        return 2
    targets = []
    for a in args.files:
        f = Path(a) if Path(a).exists() else vault / a
        try:
            f.resolve().relative_to(vault.resolve())
        except ValueError:
            print(f"ERROR: {a} is outside {vault}. The gate resolves links and areas from the vault: giving a "
                  f"clean result to a file it did not check is worse than not running. Copy the file into the vault.",
                  file=sys.stderr)
            return 2
        targets.append(f)
    targets = targets or None
    everything, found = audit(vault, targets, checks=set(args.check or []))
    unreadable = [f for f in found if f.check == "UNREADABLE"]
    failures = [f for f in found if f.check != "UNREADABLE"]
    failed = {f.file for f in failures}
    by = {c: [f for f in failures if f.check == c] for c, _ in CHECKS}
    if args.json:
        print(json.dumps({
            "files": len(everything), "failed": len(failed), "unreadable": [f.file for f in unreadable],
            "checks": {c: {"notes": len({f.file for f in fs}), "occurrences": len(fs)} for c, fs in by.items()},
            "failures": [f._asdict() for f in failures]}, ensure_ascii=False, indent=2))
    else:
        for f in unreadable:
            print(f"UNREADABLE {f.file} :: {f.msg}")
        for f in failures:
            print(f"FAILS {f.file} :: {f.check} :: {f.msg}")
        print(f"\n{len(everything)} note(s), {len(failed)} fail, {len(unreadable)} COULD NOT READ")
        for c, d in CHECKS:
            print(f"  {c:<13}{len(by[c]):>4}  {d}")
    return 3 if unreadable else (1 if failures else 0)


if __name__ == "__main__":
    sys.exit(main())
