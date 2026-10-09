#!/usr/bin/env python3
"""ask.py: ask the vault a question and check that the answer's citations exist.

Pure stdlib, no network, no API. The agent is the intelligence (see .claude/skills/cf-ask/SKILL.md);
this script only retrieves passages and verifies citations.

Usage:
    python3 tools/ask.py search "<question>" [--vault PATH] [--top N] [--links] [--json]
    python3 tools/ask.py cite <answer.md> [--vault PATH] [--log]

How search works: every vault/**/*.md is split by H1-H3 headings into chunks. Each chunk keeps its
path `note title > H2 > H3`, and that path is indexed (twice, so it weighs more) and printed. A big
section is split by paragraph into parts of up to ~1200 characters, never in the middle of a paragraph,
and every part keeps the path. A chunk id is `<path from vault, no .md>#<heading text>`, the same form
as an Obsidian heading wikilink. Text is lowercased and accent-folded; ranking is BM25 (k1=1.5,
b=0.75); ties break by id, so the order is stable. YAML frontmatter is not indexed.

`--links` adds, below the direct results, the chunks that the top results point to with [[wikilinks]],
marked `via link`, up to twice --top in total.

How cite works: every [[path#Heading]] / [[path]] in the answer must exist in the vault. rc=0 all
exist; rc=1 something is missing or the answer has no citation; rc=3 NOT_VERIFIED (the vault or the
answer could not be read, or the vault has no chunks): a check that touched nothing is never OK.

How the use of a note is measured: `cite --log`, when every citation exists, appends one JSON
line `{"date", "cited"}` to vault/memory/ask-log.jsonl. The question text is NEVER written: it can hold
something private, and the usage report only needs which notes were cited. tools/usage.py reads that file: a note that
an answer cited counts as USED. Nothing is logged when a citation fails, and `search` never writes.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent / "vault"
K1, B, MAX_CHARS = 1.5, 0.75, 1200
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
WIKILINK = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]*))?(?:\|[^\]]*)?\]\]")
TOKEN = re.compile(r"[a-z0-9]{2,}")
STOP = set("""
the a an and or of to in on at for with by from is are was were be been it its this that these those as
do does did not no what which who how why when where can could should would will if then than so
de da do das dos em no na nos nas um uma uns umas e ou para por com sem sobre ao aos que se mais como
qual quais quem onde foi sao ser tem ter ha eu me meu minha seu sua
""".split())


def norm(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in folded if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(norm(text)) if t not in STOP]


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return text


def headings_of(text: str) -> list[tuple[int, str]]:
    """Every heading (levels 1-6) outside code fences, in order."""
    out, fence = [], False
    for line in strip_frontmatter(text).splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and (m := HEADING.match(line)):
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def split_paragraphs(body: str) -> list[str]:
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", body.strip()):
        if cur and len(cur) + len(para) + 2 > MAX_CHARS:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def chunk_note(rel: str, text: str) -> list[dict]:
    """Split one note into chunks by H1-H3. rel is the path from the vault, without .md."""
    title = next((h for lv, h in headings_of(text) if lv == 1), Path(rel).name)
    cur, stack, first_h1, fence = (title, title), [], True, False
    sections: list[tuple[str, str, str]] = []  # (heading text, path, body)
    lines: list[str] = []

    def flush():
        body = "\n".join(lines).strip()
        if body:
            sections.append((cur[0], cur[1], body))
        lines.clear()

    for line in strip_frontmatter(text).splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING.match(line)
        if not (m and len(m.group(1)) <= 3):
            lines.append(line)
            continue
        flush()
        level, name = len(m.group(1)), m.group(2).strip()
        if level == 1 and first_h1:
            first_h1, stack, cur = False, [], (title, title)
        else:
            stack = [(lv, n) for lv, n in stack if lv < level] + [(level, name)]
            cur = (name, " > ".join([title] + [n for _, n in stack]))
    flush()
    return [{"id": f"{rel}#{heading}", "path": path, "text": part, "note": rel}
            for heading, path, body in sections for part in split_paragraphs(body)]


def load(vault: Path) -> tuple[list[dict], list[str]]:
    chunks, skipped = [], []
    if not vault.is_dir():
        return [], [f"{vault}: not a directory"]
    for p in sorted(vault.rglob("*.md")):
        rel_parts = p.relative_to(vault).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            skipped.append(f"{p.relative_to(vault).as_posix()}: {e.__class__.__name__}")
            continue
        chunks += chunk_note(p.relative_to(vault).with_suffix("").as_posix(), text)
    return chunks, skipped


def rank(chunks: list[dict], query: str) -> list[tuple[float, int]]:
    q = set(tokens(query))
    docs = [tokens(c["path"]) * 2 + tokens(c["text"]) for c in chunks]
    n = len(docs)
    avg = (sum(len(d) for d in docs) / n) or 1.0
    df = {t: sum(1 for d in docs if t in d) for t in q}
    scored = []
    for i, d in enumerate(docs):
        score = 0.0
        for t in q:
            tf = d.count(t)
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(d) / avg))
        if score > 0:
            scored.append((score, i))
    scored.sort(key=lambda s: (-s[0], chunks[s[1]]["id"], s[1]))
    return scored


def linked_chunks(chunks: list[dict], top: list[dict], taken: set[int], room: int) -> list[dict]:
    out = []
    for c in top:
        for m in WIKILINK.finditer(c["text"]):
            target = m.group(1).strip().removesuffix(".md")
            heading = norm(m.group(2).strip()) if m.group(2) else None
            for i, other in enumerate(chunks):
                if len(out) >= room:
                    return out
                if i in taken or other["note"] != target:
                    continue
                if heading and norm(other["id"].split("#", 1)[1]) != heading:
                    continue
                taken.add(i)
                out.append(other)
    return out


def cmd_search(a) -> int:
    chunks, skipped = load(Path(a.vault))
    for s in skipped:
        print(f"skipped {s}", file=sys.stderr)
    if not chunks:
        print("NOT_VERIFIED: the vault has no readable chunks, so nothing was searched")
        return 3
    ranked = rank(chunks, a.question)[:a.top]
    results = [dict(chunks[i], score=round(s, 4), via=None) for s, i in ranked]
    if a.links and results:
        taken = {i for _, i in ranked}
        extra = linked_chunks(chunks, results, taken, a.top)
        results += [dict(c, score=None, via="link") for c in extra]
    if a.json:
        print(json.dumps([{"rank": n, "id": r["id"], "path": r["path"], "score": r["score"], "via": r["via"],
                           "text": r["text"]} for n, r in enumerate(results, 1)], ensure_ascii=False, indent=2))
        return 0
    if not results:
        print("no results")
    for n, r in enumerate(results, 1):
        tag = "via link" if r["via"] else f"score {r['score']}"
        print(f"{n}. [[{r['id']}]]  ({tag})\n   path: {r['path']}\n{indent(r['text'])}\n")
    return 0


def indent(text: str) -> str:
    return "\n".join("   | " + ln for ln in text.splitlines())


ASK_LOG = Path("memory") / "ask-log.jsonl"
def log_consultation(vault: Path, cited: list[str], today: str | None) -> None:
    row = {"date": today or datetime.date.today().isoformat(), "cited": sorted(cited)}
    f = vault / ASK_LOG
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_cite(a) -> int:
    try:
        answer = Path(a.answer).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"NOT_VERIFIED: could not read the answer ({e.__class__.__name__})")
        return 3
    chunks, skipped = load(Path(a.vault))
    for s in skipped:
        print(f"skipped {s}", file=sys.stderr)
    if not chunks:
        print("NOT_VERIFIED: the vault has no readable chunks, so no citation could be checked")
        return 3
    cites = [(m.group(1).strip().removesuffix(".md"), (m.group(2) or "").strip()) for m in WIKILINK.finditer(answer)]
    if not cites:
        print("FAIL: no citations in the answer (every claim must cite [[path#Heading]])")
        return 1
    vault, bad, seen = Path(a.vault), [], set()
    for path, heading in cites:
        if (path, heading) in seen:
            continue
        seen.add((path, heading))
        note = vault / f"{path}.md"
        if any(part.startswith(".") for part in Path(path).parts) or not note.is_file():
            bad.append(f"[[{path}{'#' + heading if heading else ''}]]: note does not exist")
            continue
        if not heading or heading.startswith("^"):
            continue
        found = {norm(h) for _, h in headings_of(note.read_text(encoding="utf-8"))} | {norm(note.stem)}
        if norm(heading) not in found:
            bad.append(f"[[{path}#{heading}]]: the note exists but has no such heading")
    for b in bad:
        print("FAIL", b)
    if bad:
        return 1
    print(f"OK: {len(seen)} distinct citation(s) exist in the vault")
    if a.log:
        log_consultation(vault, sorted({p for p, _ in seen}), a.today)
        print(f"logged in {ASK_LOG.as_posix()}")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="ask.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("question")
    s.add_argument("--vault", default=str(VAULT))
    s.add_argument("--top", type=int, default=8)
    s.add_argument("--links", action="store_true")
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("cite")
    c.add_argument("answer")
    c.add_argument("--vault", default=str(VAULT))
    c.add_argument("--log", action="store_true", help="when every citation exists, record date and cited notes (never the question) in memory/ask-log.jsonl")
    c.add_argument("--today", help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.cmd == "search":
        if a.top < 1:
            p.error("--top must be at least 1")
        return cmd_search(a)
    return cmd_cite(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
