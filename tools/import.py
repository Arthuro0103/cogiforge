#!/usr/bin/env python3
"""import.py: brings an existing knowledge base into the vault, by COPY AND CONVERT. Stdlib only.

    python3 tools/import.py SRC [--dest DIR] [--person HANDLE] [--dry-run] [--report PATH]
    python3 tools/import.py --selftest

SRC is a folder (or one file). The default destination is `vault/inbox/imported/<name>`, where <name> is
the folder name of SRC; with `--person HANDLE` it is `vault/people/HANDLE/inbox/imported/<name>` (the person's
folder must already exist). An explicit `--dest` wins. `--vault DIR` points at another vault (tests).

What happens to each file, by extension (the original is never touched):
    .md .markdown        copied, content unchanged
    .txt                 becomes .md
    .html .htm           becomes markdown (headings, paragraphs, lists, links, code, simple tables)
    .csv .tsv            becomes a markdown table
    .json                becomes a fenced code block
    .png .jpg .jpeg .gif .svg .webp   copied as they are, same folder structure
    .pdf .docx .pptx .xlsx .epub .odt .odp .ods .rtf .doc .ppt .xls
                         converted if `docling` is importable; otherwise (or if docling fails) copied to
                         `<dest>/_unconverted/` and listed with the reason and the install command
    anything else        copied to `<dest>/_unconverted/` ("no converter")
Ignored, and listed: `.git`, `.obsidian`, `.trash`, `node_modules`, `__pycache__`, and every hidden file or
folder. Skipped, and listed: iCloud placeholders that are not downloaded ("dataless": st_blocks 0 with
st_size > 0), unreadable files, symlinks (never followed) and special files. Nothing is dropped in silence:
every file of SRC is in the report as converted, copied, unchanged, ignored, not converted or skipped,
and the count has to close.

Folder structure is kept, names are normalized to NFC, and a name that already exists with DIFFERENT
content is never overwritten: the new file gets a short content-hash suffix and the report says so.
Running it again is idempotent: identical files are reported as unchanged.

The report is `<dest>/_import-report.md` (or `--report PATH`). After the copy, `core/leak.py` runs on the
destination and the report lists file:line:type, never the data. A leak does NOT stop the copy, but the
pre-commit hook will block the commit until it is cleaned. Imported files land in an inbox, which the orphan
gate exempts: moving one to `notes/` needs a named target and a link in the body (skill `cf-import-knowledge`).
`--dry-run` plans everything, prints the report and writes nothing. An empty SRC (or one with only ignored
files) prints "nothing to import", writes nothing and is never reported as OK.
Env `COGIFORGE_IMPORT_NO_DOCLING=1` pretends docling is not installed.

rc: 0 ok · 1 some file was not converted or skipped, or a leak was found (information, not an error) ·
    2 usage or error · 3 SRC unreadable
"""
import argparse
import contextlib
import csv
import filecmp
import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"
LEAK = ROOT / "core" / "leak.py"
REPORT_NAME = "_import-report.md"
UNCONVERTED = "_unconverted"
IGNORED_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
DOC_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".epub", ".odt", ".odp", ".ods", ".rtf", ".doc", ".ppt", ".xls"}
INSTALL = "python3 -m pip install docling"
LIST_CAP = 200  # names listed per ignored folder and leak lines listed; the counts are always exact
CATEGORIES = ("converted", "copied", "unchanged", "ignored", "unconverted", "skipped")
HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def nfc(s):
    return unicodedata.normalize("NFC", s)


def clean(s):
    return "".join("?" if c in "\r\n`" else c for c in s)


# ---------------------------------------------------------------- converters

def decode_text(data):
    """(text, note). A BOM is dropped; a non-UTF-8 file is read as cp1252 and the note says so."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace"), "decoded as UTF-16"
    try:
        return data.decode("utf-8-sig"), ""
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "not UTF-8: decoded as cp1252"


def fence_for(text):
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


class HtmlToMarkdown(HTMLParser):
    """Small and forgiving: headings, paragraphs, lists, links, code, quotes and simple tables."""

    BLOCKS = {"p", "div", "section", "article", "header", "footer", "main", "nav", "aside", "figure",
              "figcaption", "dl", "dt", "dd", "details", "summary", "address"}
    SKIP = {"script", "style", "head", "template", "noscript", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []        # (text, kind)
        self.buf = ""
        self.skip = 0
        self.title = ""
        self.in_title = False
        self.heading = 0
        self.lists = []         # ["ul"|"ol", counter]
        self.prefix = ""
        self.pre = None
        self.links = []         # (href, start index in buf)
        self.quote = 0
        self.rows, self.row, self.cell, self.in_cell, self.header_row = [], [], "", False, False
        self.has_h1 = False

    # -- output
    def emit(self, text, kind):
        if text:
            if self.quote:
                text = "\n".join("> " * self.quote + l for l in text.split("\n"))
            self.blocks.append((text, kind))

    def flush(self):
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", self.buf).strip()
        self.buf = ""
        self.links = []
        if not text:
            return
        kind = "p"
        if self.prefix:  # the first text after <li> carries the list marker
            text = self.prefix + text.replace("\n", "\n" + " " * len(self.prefix))
            self.prefix, kind = "", "li"
        self.emit(text, kind)

    # -- tags
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip or self.pre is not None:
            return
        if self.in_cell and tag not in ("td", "th", "tr", "table"):
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.flush()
            self.heading = int(tag[1])
            self.has_h1 = self.has_h1 or tag == "h1"
        elif tag in self.BLOCKS:
            self.flush()
        elif tag in ("ul", "ol"):
            self.flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self.flush()
            if not self.lists:
                self.lists.append(["ul", 0])
            self.lists[-1][1] += 1
            marker = "- " if self.lists[-1][0] == "ul" else f"{self.lists[-1][1]}. "
            self.prefix = "  " * (len(self.lists) - 1) + marker
        elif tag == "pre":
            self.flush()
            self.pre = ""
        elif tag == "code":
            self.buf += "`"
        elif tag in ("strong", "b"):
            self.buf += "**"
        elif tag in ("em", "i"):
            self.buf += "*"
        elif tag == "a":
            self.links.append((a.get("href") or "", len(self.buf)))
        elif tag == "br":
            self.buf += "  \n"
        elif tag == "hr":
            self.flush()
            self.emit("---", "p")
        elif tag == "blockquote":
            self.flush()
            self.quote += 1
        elif tag == "img":
            alt, src = a.get("alt") or "", a.get("src") or ""
            self.buf += f"![{alt}]({src})" if src else alt
        elif tag == "table":
            self.flush()
            self.rows = []
        elif tag == "tr":
            self.row, self.header_row = [], False
        elif tag in ("td", "th"):
            self.in_cell, self.cell = True, ""
            self.header_row = self.header_row or tag == "th"

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "pre" and self.pre is not None:
            code, self.pre = self.pre.strip("\n"), None
            self.emit(f"{fence_for(code)}\n{code}\n{fence_for(code)}", "code")
            return
        if self.pre is not None:
            return
        if self.in_cell and tag not in ("td", "th", "tr", "table"):
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = re.sub(r"\s+", " ", self.buf).strip()
            self.buf = ""
            if text:
                self.emit("#" * self.heading + " " + text, "p")
            self.heading = 0
        elif tag in self.BLOCKS:
            self.flush()
        elif tag == "li":
            self.flush()
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
        elif tag == "code":
            self.buf += "`"
        elif tag in ("strong", "b"):
            self.buf += "**"
        elif tag in ("em", "i"):
            self.buf += "*"
        elif tag == "a" and self.links:
            href, start = self.links.pop()
            if href:
                text = self.buf[start:]
                self.buf = self.buf[:start] + f"[{text.strip() or href}]({href})"
        elif tag == "blockquote":
            self.flush()
            self.quote = max(0, self.quote - 1)
        elif tag in ("td", "th") and self.in_cell:
            self.row.append(re.sub(r"\s+", " ", self.cell).strip().replace("|", "\\|"))
            self.in_cell = False
        elif tag == "tr" and self.row:
            self.rows.append((self.row, self.header_row))
        elif tag == "table":
            self.emit_table()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.skip:
            return
        if self.pre is not None:
            self.pre += data
        elif self.in_cell:
            self.cell += data
        else:
            self.buf += re.sub(r"\s+", " ", data)

    def emit_table(self):
        rows, self.rows = self.rows, []
        if not rows:
            return
        width = max(len(r) for r, _ in rows)
        lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r, _ in rows]
        lines.insert(1, "|" + " --- |" * width)
        self.emit("\n".join(lines), "p")

    def markdown(self):
        self.flush()
        joined = ""
        prev = None
        for i, (text, kind) in enumerate(self.blocks):
            sep = "" if i == 0 else ("\n" if kind == "li" and prev == "li" else "\n\n")
            joined += sep + text
            prev = kind
        if not self.has_h1 and self.title.strip():
            joined = "# " + re.sub(r"\s+", " ", self.title).strip() + ("\n\n" + joined if joined else "")
        return joined.strip() + "\n" if joined.strip() else ""


def html_to_md(data):
    m = re.search(rb"charset\s*=\s*[\"']?([\w-]+)", data[:2048], re.I)
    text = None
    if m:
        try:
            text = data.decode(m.group(1).decode("ascii"), errors="replace")
        except LookupError:
            text = None
    if text is None:
        text = decode_text(data)[0]
    p = HtmlToMarkdown()
    p.feed(text)
    p.close()
    return p.markdown().encode("utf-8")


def csv_to_md(data, delimiter=None):
    text = decode_text(data)[0]
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    rows = [r for r in csv.reader(text.splitlines(), delimiter=delimiter) if r]
    if not rows:
        return b"_(empty file)_\n"
    width = max(len(r) for r in rows)

    def cell(c):
        return c.replace("|", "\\|").replace("\n", "<br>").strip()

    lines = ["| " + " | ".join([cell(c) for c in r] + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return ("\n".join(lines) + "\n").encode("utf-8")


def json_to_md(data):
    text = decode_text(data)[0].strip("\n")
    f = fence_for(text)
    return f"{f}json\n{text}\n{f}\n".encode("utf-8")


def docling_available():
    if os.environ.get("COGIFORGE_IMPORT_NO_DOCLING"):
        return False
    try:
        return importlib.util.find_spec("docling") is not None
    except (ImportError, ValueError):
        return False


_converter = []


def docling_to_md(path):
    if not _converter:
        from docling.document_converter import DocumentConverter
        _converter.append(DocumentConverter())
    return _converter[0].convert(str(path)).document.export_to_markdown().encode("utf-8")


# ---------------------------------------------------------------- walking the source

def walk(src):
    """Yields (relpath, kind, reason). kind: file | ignored | skipped. Never follows a symlink."""
    def rec(d, rel, ignored_by):
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError as e:
            yield (rel or ".", "skipped", f"folder not readable ({e.strerror})")
            return
        for e in entries:
            r = f"{rel}/{e.name}" if rel else e.name
            is_dir = e.is_dir(follow_symlinks=False)
            if ignored_by:
                if is_dir:
                    yield from rec(e.path, r, ignored_by)
                else:
                    yield (r, "ignored", ignored_by)
            elif e.is_symlink():
                yield (r, "skipped", "symlink (never followed)")
            elif is_dir:
                if e.name in IGNORED_DIRS:
                    yield from rec(e.path, r, f"ignored folder `{e.name}/`")
                elif e.name.startswith("."):
                    yield from rec(e.path, r, "hidden folder")
                else:
                    yield from rec(e.path, r, None)
            elif e.name.startswith("."):
                yield (r, "ignored", "hidden file")
            elif e.is_file(follow_symlinks=False):
                yield (r, "file", "")
            else:
                yield (r, "skipped", "not a regular file")

    if src.is_file():
        yield (src.name, "ignored", "hidden file") if src.name.startswith(".") else (src.name, "file", "")
    else:
        yield from rec(src, "", None)


def is_dataless(st):
    return st.st_size > 0 and getattr(st, "st_blocks", 1) == 0


# ---------------------------------------------------------------- placing the output

class Dest:
    def __init__(self, root, dry):
        self.root, self.dry = root, dry
        self.taken = {}  # lowercase relpath -> payload that was placed this run

    @staticmethod
    def digest(payload):
        h = hashlib.sha256()
        if isinstance(payload, bytes):
            h.update(payload)
        else:
            with open(payload, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        return h.hexdigest()

    def same(self, rel, payload):
        """True if what is already at rel (on disk or placed this run) has the payload's content."""
        placed = self.taken.get(rel.lower())
        target = self.root / rel
        if placed is not None:
            return self.digest(placed) == self.digest(payload)
        if not target.is_file():
            return False
        if isinstance(payload, bytes):
            return target.read_bytes() == payload
        return filecmp.cmp(target, payload, shallow=False)

    def busy(self, rel):
        return rel.lower() in self.taken or (self.root / rel).exists()

    def place(self, rel, payload):
        """(final relpath, status) with status new | unchanged | renamed. Never overwrites different content."""
        if not self.busy(rel):
            final, status = rel, "new"
        elif self.same(rel, payload):
            return rel, "unchanged"
        else:
            stem, dot, ext = rel.rpartition(".")
            if not dot or "/" in ext:
                stem, ext = rel, ""
            n, tag = 0, self.digest(payload)[:8]
            while True:
                final = f"{stem}.{tag}{'' if not n else '-' + str(n)}{'.' + ext if ext else ''}"
                if not self.busy(final):
                    status = "renamed"
                    break
                if self.same(final, payload):
                    return final, "unchanged"
                n += 1
        self.taken[final.lower()] = payload
        if not self.dry:
            target = self.root / final
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                if isinstance(payload, bytes):
                    target.write_bytes(payload)
                else:
                    shutil.copyfile(payload, target)
            except OSError:
                target.unlink(missing_ok=True)
                self.taken.pop(final.lower(), None)
                raise
        return final, status


def with_suffix(rel, new):
    p = Path(rel)
    return p.with_suffix(new).as_posix()


def import_tree(src, dest_root, dry):
    """List of entries {src, cat, dest, reason, renamed}, sorted by source path."""
    dest = Dest(dest_root, dry)
    entries = []
    for rel, kind, reason in walk(src):
        e = {"src": nfc(rel), "cat": kind, "dest": None, "reason": reason, "renamed": False}
        entries.append(e)
        if kind != "file":
            continue
        path = src / rel if src.is_dir() else src
        out = nfc(rel)
        ext = Path(rel).suffix.lower()
        try:
            st = path.stat()
            if is_dataless(st):
                e.update(cat="skipped", reason="iCloud placeholder not downloaded (dataless): materialize it "
                                               "(open it or 'Download Now' in Finder) and run again")
                continue
            payload, cat, note = None, "converted", ""
            if ext in (".md", ".markdown"):
                payload, cat = path, "copied"
                out = with_suffix(out, ".md") if ext == ".markdown" else out
            elif ext in IMAGES:
                payload, cat = path, "copied"
            elif ext == ".txt":
                text, note = decode_text(path.read_bytes())
                payload, out = text.encode("utf-8"), with_suffix(out, ".md")
            elif ext in (".html", ".htm"):
                payload, out = html_to_md(path.read_bytes()), with_suffix(out, ".md")
            elif ext in (".csv", ".tsv"):
                payload = csv_to_md(path.read_bytes(), "\t" if ext == ".tsv" else None)
                out = with_suffix(out, ".md")
            elif ext == ".json":
                payload, out = json_to_md(path.read_bytes()), with_suffix(out, ".md")
            elif ext in DOC_EXTS:
                if not docling_available():
                    raise Unconverted(f"needs docling, which is not installed: `{INSTALL}`, then run again; "
                                      f"the old copy in {UNCONVERTED}/ can then be deleted")
                try:
                    payload, out = docling_to_md(path), with_suffix(out, ".md")
                except Exception as exc:  # docling raises many types; the file must still be accounted for
                    raise Unconverted(f"docling could not convert it ({type(exc).__name__})") from exc
            else:
                raise Unconverted(f"no converter for `{ext or 'files without extension'}`")
            if cat == "converted" and not payload.strip():
                note = (note + "; " if note else "") + "the converted output is empty"
            final, status = dest.place(out, payload)
        except Unconverted as u:
            try:
                final, status = dest.place(f"{UNCONVERTED}/{nfc(rel)}", path)
                e.update(cat="unconverted", dest=final, reason=str(u), renamed=status == "renamed")
                if status == "unchanged":
                    e["reason"] += " (identical copy already there)"
            except OSError as oe:
                e.update(cat="skipped", reason=f"could not copy ({oe.strerror})")
            continue
        except (OSError, csv.Error, UnicodeError) as exc:
            reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else type(exc).__name__
            e.update(cat="skipped", reason=f"could not be read, converted or written ({reason})")
            continue
        if status == "unchanged":
            e.update(cat="unchanged", dest=final, reason="identical content already at the destination")
        else:
            e.update(cat=cat, dest=final, reason=note, renamed=status == "renamed")
    return entries


class Unconverted(Exception):
    pass


# ---------------------------------------------------------------- leak scan and report

LEAK_LINE = re.compile(r"^(.*):(\d+): ([\w-]+)$")


def scan_leaks(dest_root):
    """([(file, line, type)], note). note is '' when the scan ran completely."""
    if not LEAK.is_file():
        return [], "core/leak.py not found: the destination was NOT scanned"
    r = subprocess.run([sys.executable, str(LEAK), "."], capture_output=True, text=True, cwd=dest_root)
    found = []
    for line in r.stdout.splitlines():
        m = LEAK_LINE.match(line)
        if m:
            found.append((m.group(1), int(m.group(2)), m.group(3)))
    notes = []  # fixed wording: leak.py's own text carries the machine's home path, which must not enter a report
    if "private blocklist missing" in r.stdout:
        notes.append("the private blocklist is missing: only the generic patterns ran (see core/leak.py)")
    unreadable = [l for l in r.stdout.splitlines() if l.endswith(": unreadable")]
    if unreadable:
        notes.append(f"{len(unreadable)} file(s) could not be read by the scan")
    if r.returncode not in (0, 1, 3) and not unreadable:
        notes.append(f"leak.py exited with rc={r.returncode}")
    return found, " ".join(notes)


def counts_of(entries):
    return {c: sum(1 for e in entries if e["cat"] == c) for c in CATEGORIES}


def bullet(e, with_dest=True):
    line = f"- `{clean(e['src'])}`"
    if with_dest and e["dest"]:
        line += f" -> `{clean(e['dest'])}`"
    if e["reason"]:
        line += f" ({e['reason']})"
    return line


def build_report(name, dest_label, entries, leaks, leak_note, dry, dest_in_inbox):
    counts = counts_of(entries)
    out = [f"# Import report: {clean(name)}", ""]
    if leaks:
        kinds = sorted({k for _, _, k in leaks})
        out += [f"> **WARNING: {len(leaks)} possible personal-data occurrence(s) in the destination "
                f"({', '.join(kinds)}).** The copy was NOT stopped, but the pre-commit hook will BLOCK the commit "
                "of these files until they are cleaned. The list below gives file:line:type, never the data.", ""]
    if dry:
        out += ["> Dry run: nothing was written.", ""]
    out += [f"Source folder: `{clean(name)}`", f"Destination: `{clean(dest_label)}`", "",
            "| | files |", "|---|---|", f"| in the source | {len(entries)} |"]
    out += [f"| {c} | {counts[c]} |" for c in CATEGORIES]
    out += ["", f"The count closes: {len(entries)} = " + " + ".join(str(counts[c]) for c in CATEGORIES) + ".", ""]
    titles = {
        "converted": "Converted to markdown",
        "copied": "Copied as they are",
        "unchanged": "Unchanged (already there, identical)",
        "unconverted": f"Not converted (copied to `{UNCONVERTED}/`)",
        "skipped": "Skipped (not copied)",
    }
    for c in ("converted", "copied", "unchanged", "unconverted", "skipped"):
        items = [e for e in entries if e["cat"] == c]
        if items:
            out += [f"## {titles[c]} ({len(items)})", ""] + [bullet(e) for e in items] + [""]
    ignored = [e for e in entries if e["cat"] == "ignored"]
    if ignored:
        out += [f"## Ignored ({len(ignored)})", ""]
        by_reason = {}
        for e in ignored:
            by_reason.setdefault(e["reason"], []).append(e)
        for reason, items in sorted(by_reason.items()):
            out.append(f"- {reason}: {len(items)} file(s)")
            out += [f"  - `{clean(e['src'])}`" for e in items[:LIST_CAP]]
            if len(items) > LIST_CAP:
                out.append(f"  - ... and {len(items) - LIST_CAP} more (the count above is exact)")
        out.append("")
    renamed = [e for e in entries if e["renamed"]]
    if renamed:
        out += [f"## Name collisions ({len(renamed)})", "",
                "Same name, different content: nothing was overwritten, the new file got a content-hash suffix.", ""]
        out += [f"- `{clean(e['src'])}` -> `{clean(e['dest'])}`" for e in renamed] + [""]
    out += ["## Personal-data scan", ""]
    if dry:
        out.append("Not run: a dry run writes nothing to scan.")
    else:
        if leaks:
            out += [f"{len(leaks)} occurrence(s) found by `core/leak.py`:", ""]
            out += [f"- `{clean(f)}:{n}:{k}`" for f, n, k in leaks[:LIST_CAP]]
            if len(leaks) > LIST_CAP:
                out.append(f"- ... and {len(leaks) - LIST_CAP} more")
        elif not leak_note:
            out.append("`core/leak.py` found nothing in the text files of the destination.")
        if leak_note:
            out += ["", f"NOT_VERIFIED: {leak_note}"]
        out += ["", f"Binary files (including everything in `{UNCONVERTED}/`) are not scanned: open them before sharing."]
    out += ["", "## Next step: triage", ""]
    if dest_in_inbox:
        out.append("The imported files sit in an inbox, which the orphan gate exempts, so they will not block a commit "
                   "for lacking links.")
    else:
        out.append("**The destination is not inside an inbox folder**, so the orphan gate will judge every imported note.")
    out += ["Moving one into `notes/` is a decision, not a copy: it needs a **named target** (project, article, question, "
            "task or none) and a **link in the body** that is real. Use the `cf-import-knowledge` skill: it proposes, you approve.",
            "Links inside the imported files still point where they pointed in the old base; some will be dead here."]
    if any("docling" in e["reason"] for e in entries if e["cat"] == "unconverted"):
        out += ["", f"To convert the documents listed above: `{INSTALL}`, then run the same command again "
                    f"(identical files are skipped)."]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def resolve_dest(args, src, vault):
    """(Path, error). The destination folder, or an error message."""
    name = nfc(src.name) or "import"
    if args.person is not None and not HANDLE_RE.match(args.person):
        return None, f"invalid --person handle: {args.person!r}"
    person_dir = None
    if args.person is not None:
        person_dir = vault / "people" / args.person
        if not person_dir.is_dir():
            return None, f"no such person: vault/people/{args.person}/ does not exist (create it first)"
    if args.dest:
        return Path(args.dest), None
    base = person_dir / "inbox" / "imported" if person_dir else vault / "inbox" / "imported"
    return base / name, None


def inside(child, parent):
    c, p = child.resolve(), parent.resolve()
    return c == p or p in c.parents


def label_of(dest, vault):
    try:
        return dest.resolve().relative_to(vault.resolve().parent).as_posix()
    except ValueError:
        return f"(outside the repo)/{dest.name}"


def run(args):
    vault = Path(args.vault) if args.vault else VAULT
    if not args.src:
        print("ERROR: SRC is required (see --help)", file=sys.stderr)
        return 2
    src = Path(args.src)
    if not os.access(src, os.R_OK) or not (src.is_dir() or src.is_file()):
        print(f"ERROR: source is not readable (or does not exist): {args.src}", file=sys.stderr)
        return 3
    if src.is_dir():
        try:
            os.listdir(src)
        except OSError as e:
            print(f"ERROR: source folder cannot be listed ({e.strerror}): {args.src}", file=sys.stderr)
            return 3
    dest, err = resolve_dest(args, src, vault)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    if src.is_dir() and (inside(dest, src) or inside(src, dest)):
        print("ERROR: the destination and the source cannot contain each other; nothing was written.", file=sys.stderr)
        return 2

    entries = import_tree(src, dest, args.dry_run)
    counts = counts_of(entries)
    if sum(counts.values()) != len(entries):
        print("ERROR: internal: the count does not close; nothing was reported as done.", file=sys.stderr)
        return 2
    name = nfc(src.name)
    label = label_of(dest, vault)
    imported = len(entries) - counts["ignored"]
    if imported == 0:
        print(f"nothing to import: {len(entries)} file(s) seen in the source, {counts['ignored']} ignored. "
              "Nothing was written.")
        return 0

    leaks, leak_note = ([], "")
    if not args.dry_run:
        leaks, leak_note = scan_leaks(dest)
    in_inbox = "inbox" in Path(label).parts
    report = build_report(name, label, entries, leaks, leak_note, args.dry_run, in_inbox)
    if args.dry_run:
        print(report)
    else:
        target = Path(args.report) if args.report else dest / REPORT_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")
        print(f"report: {target if args.report else label + '/' + REPORT_NAME}")
    parts = ", ".join(f"{counts[c]} {c}" for c in CATEGORIES)
    print(f"{len(entries)} file(s) in the source = {parts}")
    if leaks:
        print(f"WARNING: {len(leaks)} possible personal-data occurrence(s); the commit will be blocked until cleaned.")
    if leak_note:
        print(f"{leak_note} (NOT_VERIFIED, not OK)")
    needs_look = counts["unconverted"] + counts["skipped"]
    if needs_look:
        print(f"{needs_look} file(s) were not converted or were skipped: see the report.")
    return 1 if (needs_look or leaks) else 0


def selftest():
    env_keep = {k: os.environ.get(k) for k in ("COGIFORGE_IMPORT_NO_DOCLING", "LEAK_BLOCKLIST")}
    os.environ["COGIFORGE_IMPORT_NO_DOCLING"] = "1"
    os.environ["LEAK_BLOCKLIST"] = os.path.join(tempfile.gettempdir(), "import-selftest-absent-list.txt")
    results = []

    def check(label, ok):
        results.append(ok)
        print(("ok   " if ok else "FAIL ") + label)

    def call(*argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return run(parser().parse_args(list(argv)))

    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, vault = td / "base", td / "vault"
            (vault / "inbox").mkdir(parents=True)
            (src / "sub").mkdir(parents=True)
            (src / ".obsidian").mkdir()
            (src / ".obsidian" / "app.json").write_text("{}")
            (src / "a.md").write_text("# A\n\n[[b]]\n")
            (src / "sub" / "b.txt").write_text("plain\n")
            (src / "page.html").write_text("<h1>T</h1><p>one <a href='x.md'>two</a></p><ul><li>i</li></ul>")
            (src / "t.csv").write_text("a,b\n1,2\n")
            (src / "d.json").write_text('{"k": 1}')
            (src / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
            (src / "img.png").write_bytes(b"\x89PNG fake")
            rc1 = call(str(src), "--vault", str(vault))
            dest = vault / "inbox" / "imported" / "base"
            report = (dest / REPORT_NAME).read_text()
            check("first run: rc 1 because the pdf was not converted", rc1 == 1)
            check("md copied unchanged", (dest / "a.md").read_text() == "# A\n\n[[b]]\n")
            check("html became markdown", "# T" in (dest / "page.md").read_text())
            check("csv became a table", "| a | b |" in (dest / "t.md").read_text())
            check("pdf went to _unconverted and is in the report",
                  (dest / UNCONVERTED / "doc.pdf").is_file() and "doc.pdf" in report)
            check("the count closes in the report", "| in the source | 8 |" in report and "The count closes: 8 = " in report)
            before = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
            rc2 = call(str(src), "--vault", str(vault))
            after = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
            check("second run is idempotent (same files, rc 1 again for the pdf)", before == after and rc2 == 1)
            (src / "a.md").write_text("# A changed\n")
            call(str(src), "--vault", str(vault))
            check("collision keeps the old file and adds a suffixed one",
                  (dest / "a.md").read_text() == "# A\n\n[[b]]\n"
                  and len([p for p in dest.glob("a.*.md")]) == 1)
            empty = td / "empty"
            empty.mkdir()
            check("empty folder: rc 0 and writes nothing", call(str(empty), "--vault", str(vault)) == 0
                  and not (vault / "inbox" / "imported" / "empty").exists())
            check("person that does not exist: rc 2", call(str(src), "--vault", str(vault), "--person", "nobody") == 2)
            check("missing source: rc 3", call(str(td / "nope"), "--vault", str(vault)) == 3)
    finally:
        for k, v in env_keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("selftest:", "OK" if all(results) else "FAILED")
    return 0 if all(results) else 1


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?")
    ap.add_argument("--dest")
    ap.add_argument("--person")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report")
    ap.add_argument("--vault")
    ap.add_argument("--selftest", action="store_true")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
