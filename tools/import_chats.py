#!/usr/bin/env python3
"""import_chats.py: turn a chat export (claude.ai or ChatGPT) into one Markdown note per conversation.

Pure stdlib, no network, no API. Reads the `conversations.json` of an export, or the export .zip
itself (every `conversations.json` / `conversations-NNN.json` inside it), and writes one .md per
conversation into `vault/inbox/chats/` (or `--dest`). Nothing is ever overwritten.

Usage:
    python3 tools/import_chats.py <conversations.json | export.zip> [--dest DIR] [--dry-run]
    python3 tools/import_chats.py --selftest

How the format is detected (by structure, never by file name):
  * ChatGPT keeps each conversation as a tree: `mapping` (id -> node with `parent`) plus
    `current_node`. The tool follows `current_node` up to the root through `parent` and reverses the
    path, so an abandoned branch (a regenerated answer, an edited prompt) is NOT imported.
    Only `user` and `assistant` messages with visible text are kept; system and tool messages are not.
  * claude.ai keeps a flat list `chat_messages` (`sender` is `human` or `assistant`). Only the text
    blocks are kept; attachment file names are listed under the message, their contents are not copied.

Each note has the frontmatter `type: chat`, `source: claude|chatgpt`, `date`, `title`, then one
`## User` or `## Assistant` heading per turn. A line inside a turn that would look like a speaker
heading is escaped with a backslash, so the two voices cannot be confused. `[[` is written as `[ [`
so that chat text can never create a wikilink that the link gate would call broken.

A conversation with no text is reported and skipped; an empty file is never written. A file that
already exists is never overwritten (re-running the import reports "already imported").

The export holds EVERYTHING the person ever typed. Run `python3 core/leak.py .` before committing,
and remember that in a shared repository every member can read what is committed.

rc: 0 everything written (or, with --dry-run, would be written) · 1 some conversations were skipped
· 2 usage error · 3 unreadable file or format not recognized (never reported as "0 conversations, OK")
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = ROOT / "vault" / "inbox" / "chats"
MEMBER = re.compile(r"^conversations(-\d+)?\.json$")
SPEAKER_LINE = re.compile(r"^(#{1,2})([ \t]+(?:User|Assistant)[ \t]*)$", re.M)
PRIVACY = ("PRIVACY: an export contains everything you ever said in these chats. Run "
           "`python3 core/leak.py .` before you commit, and remember that everyone who can read this "
           "repository can read what you commit.")


class FormatError(Exception):
    """The file could not be read, or is not a chat export we recognize (rc 3)."""


# ---------------------------------------------------------------- loading

def load_conversations(src: Path):
    """Return the list of raw conversation objects, or raise FormatError."""
    try:
        if zipfile.is_zipfile(src):
            items = []
            with zipfile.ZipFile(src) as zf:
                names = sorted(n for n in zf.namelist() if MEMBER.match(Path(n).name))
                if not names:
                    raise FormatError("format not recognized: the zip has no conversations.json")
                for n in names:
                    items.extend(_parse(zf.read(n), n))
            return items
        return _parse(src.read_bytes(), src.name)
    except FormatError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as e:
        raise FormatError(f"could not read {src}: {e}")


def _parse(raw: bytes, label: str):
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as e:
        raise FormatError(f"format not recognized: {label} is not valid JSON ({e.__class__.__name__})")
    if not isinstance(data, list):
        raise FormatError(f"format not recognized: {label} is not a list of conversations")
    if not data:
        raise FormatError(f"format not recognized: {label} holds an empty list, nothing was checked")
    return data


def detect(conv) -> str | None:
    if isinstance(conv, dict):
        if isinstance(conv.get("mapping"), dict):
            return "chatgpt"
        if isinstance(conv.get("chat_messages"), list):
            return "claude"
    return None


# ---------------------------------------------------------------- extraction

def _date(value) -> str:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d")
        if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
            return value[:10]
    except (OverflowError, OSError, ValueError):
        pass
    return "unknown"


def _claude_turns(conv):
    turns = []
    for m in conv["chat_messages"]:
        if not isinstance(m, dict):
            continue
        role = {"human": "user", "assistant": "assistant"}.get(m.get("sender"))
        if role is None:
            continue
        blocks = m.get("content")
        parts = []
        if isinstance(blocks, list) and blocks:
            parts = [b["text"] for b in blocks
                     if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
        elif isinstance(m.get("text"), str):
            parts = [m["text"]]
        text = "\n\n".join(p.strip() for p in parts if p.strip())
        names = [a.get("file_name") for key in ("attachments", "files") for a in (m.get(key) or [])
                 if isinstance(a, dict) and a.get("file_name")]
        if names:
            text = (text + "\n\n" if text else "") + "_Attachments (names only): " + ", ".join(names) + "_"
        if text:
            turns.append((role, text))
    return turns


def _gpt_text(msg):
    content = msg.get("content") or {}
    ctype = content.get("content_type")
    if ctype == "code" and isinstance(content.get("text"), str):
        return "```\n" + content["text"].strip("\n") + "\n```" if content["text"].strip() else ""
    if ctype not in ("text", "multimodal_text"):
        return ""
    out = []
    for p in content.get("parts") or []:
        if isinstance(p, str):
            if p.strip():
                out.append(p.strip())
        elif isinstance(p, dict):
            t = p.get("text")
            out.append(t.strip() if isinstance(t, str) and t.strip() else "_[non-text part not imported]_")
    return "\n\n".join(out)


def _gpt_path(conv):
    mapping = conv["mapping"]
    node = conv.get("current_node")
    if node not in mapping:
        # no usable current_node: take the leaf whose message is newest
        leaves = [k for k, v in mapping.items() if isinstance(v, dict) and not v.get("children")]
        def stamp(k):
            m = mapping[k].get("message") or {}
            return m.get("create_time") or 0
        node = max(leaves, key=stamp) if leaves else None
    path, seen = [], set()
    while node is not None and node in mapping and node not in seen:
        seen.add(node)
        path.append(mapping[node])
        node = mapping[node].get("parent")
    return list(reversed(path))


def _gpt_turns(conv):
    turns = []
    for n in _gpt_path(conv):
        msg = n.get("message") if isinstance(n, dict) else None
        if not isinstance(msg, dict):
            continue
        role = (msg.get("author") or {}).get("role")
        if role not in ("user", "assistant"):
            continue
        if (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
            continue
        text = _gpt_text(msg)
        if text:
            turns.append((role, text))
    return turns


# ---------------------------------------------------------------- rendering

def _clean_text(text: str) -> str:
    text = text.replace("[[", "[ [")
    return SPEAKER_LINE.sub(lambda m: "\\" + m.group(1) + m.group(2), text)


def _clean_title(title) -> str:
    t = re.sub(r"\s+", " ", title if isinstance(title, str) else "").strip()
    return t.replace('"', "'").replace("\\", "/").replace("[[", "[ [")


def _slug(title: str) -> str:
    folded = unicodedata.normalize("NFKD", title.lower())
    ascii_ = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:50].strip("-") or "chat"


def convert(conv, index: int):
    """-> (source, date, title, turns, id8)."""
    source = detect(conv)
    turns = _claude_turns(conv) if source == "claude" else _gpt_turns(conv)
    raw_date = conv.get("created_at") if source == "claude" else conv.get("create_time")
    title = _clean_title(conv.get("name") if source == "claude" else conv.get("title"))
    if not title:
        first = next((t for r, t in turns if r == "user"), "")
        title = _clean_title(first.splitlines()[0][:60]) if first else ""
    title = title or "untitled"
    ident = str(conv.get("uuid") or conv.get("id") or conv.get("conversation_id") or "")
    if not ident:
        ident = f"{index}:{title}:{raw_date}"
    return source, _date(raw_date), title, turns, hashlib.sha1(ident.encode()).hexdigest()[:8]


def render(source, date, title, turns) -> str:
    out = ["---", "type: chat", f"source: {source}", f"date: {date}", f'title: "{title}"', "---", f"# {title}", ""]
    for role, text in turns:
        out += [f"## {'User' if role == 'user' else 'Assistant'}", "", _clean_text(text), ""]
    return "\n".join(out)


# ---------------------------------------------------------------- run

def run(src: Path, dest: Path, dry: bool, out=print):
    """Return the rc. `out` receives each report line."""
    try:
        convs = load_conversations(src)
    except FormatError as e:
        out(f"error: {e}")
        return 3
    if not any(detect(c) for c in convs):
        out("error: format not recognized: no conversation has `mapping` (ChatGPT) or `chat_messages` (claude.ai). Nothing was read.")
        return 3
    written, skipped, planned = 0, [], set()
    for i, conv in enumerate(convs):
        if detect(conv) is None:
            skipped.append(("unrecognized structure", f"item {i}"))
            continue
        source, date, title, turns, id8 = convert(conv, i)
        if not turns:
            skipped.append(("no text", f"{source} '{title}'"))
            continue
        name = f"{date}-{_slug(title)}-{id8}.md"
        if name in planned or (dest / name).exists():
            if (dest / name).exists() and name not in planned:
                skipped.append(("already imported", name))
                continue
            stem, n = name[:-3], 2
            while f"{stem}-{n}.md" in planned or (dest / f"{stem}-{n}.md").exists():
                n += 1
            name = f"{stem}-{n}.md"
        planned.add(name)
        if not dry:
            dest.mkdir(parents=True, exist_ok=True)
            with open(dest / name, "x", encoding="utf-8") as f:
                f.write(render(source, date, title, turns))
        written += 1
        out(f"  {'would write' if dry else 'wrote'} {name}")
    reasons = {}
    for why, _ in skipped:
        reasons[why] = reasons.get(why, 0) + 1
    out(f"read {len(convs)} · {'would write' if dry else 'written'} {written} · skipped {len(skipped)}"
        + (" (" + ", ".join(f"{n} {w}" for w, n in sorted(reasons.items())) + ")" if skipped else ""))
    for why, what in skipped:
        out(f"  skipped ({why}): {what}")
    if dry:
        out("dry run: nothing was written")
    out(PRIVACY)
    return 1 if skipped else 0


# ---------------------------------------------------------------- selftest

def _selftest() -> int:
    gpt = [{"title": "Plan", "create_time": 1767225600, "current_node": "c", "mapping": {
        "r": {"id": "r", "parent": None, "children": ["a"], "message": None},
        "a": {"id": "a", "parent": "r", "children": ["b", "x"], "message": {
            "author": {"role": "user"}, "content": {"content_type": "text", "parts": ["question one"]}}},
        "x": {"id": "x", "parent": "a", "children": [], "message": {
            "author": {"role": "assistant"}, "content": {"content_type": "text", "parts": ["ABANDONED"]}}},
        "b": {"id": "b", "parent": "a", "children": ["c"], "message": {
            "author": {"role": "assistant"}, "content": {"content_type": "text", "parts": ["kept answer"]}}},
        "c": {"id": "c", "parent": "b", "children": [], "message": {
            "author": {"role": "user"}, "content": {"content_type": "text", "parts": ["## Assistant"]}}}}}]
    cla = [{"uuid": "u1", "name": "Hello", "created_at": "2026-01-02T10:00:00Z", "chat_messages": [
        {"sender": "human", "text": "hi"}, {"sender": "assistant", "text": "hello"}]}]
    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for label, data in (("chatgpt", gpt), ("claude", cla)):
            f = tmp / f"{label}.json"
            f.write_text(json.dumps(data), encoding="utf-8")
            dest = tmp / f"out-{label}"
            rc = run(f, dest, False, out=lambda s: None)
            files = list(dest.glob("*.md"))
            body = files[0].read_text(encoding="utf-8") if files else ""
            checks.append((f"{label}: rc 0 and one file", rc == 0 and len(files) == 1))
            checks.append((f"{label}: frontmatter has the source", f"source: {label}" in body and "type: chat" in body))
        gbody = next((tmp / "out-chatgpt").glob("*.md")).read_text(encoding="utf-8")
        checks.append(("chatgpt: the abandoned branch is not imported", "ABANDONED" not in gbody and "kept answer" in gbody))
        checks.append(("chatgpt: a fake speaker heading is escaped", "\n\\## Assistant" in gbody))
        bad = tmp / "bad.json"
        bad.write_text('{"not": "a list"}', encoding="utf-8")
        checks.append(("unknown format gives rc 3", run(bad, tmp / "o3", False, out=lambda s: None) == 3 and not (tmp / "o3").exists()))
        empty = tmp / "empty.json"
        empty.write_text(json.dumps([{"uuid": "z", "name": "e", "chat_messages": []}]), encoding="utf-8")
        checks.append(("a conversation with no text is skipped (rc 1, no file)",
                       run(empty, tmp / "o4", False, out=lambda s: None) == 1 and not list((tmp / "o4").glob("*.md"))))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("ok    " if ok else "FAIL  ") + name)
    print(f"selftest: {len(checks) - len(failed)} of {len(checks)} checks passed")
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Convert a claude.ai or ChatGPT export into one .md per conversation.")
    ap.add_argument("source", nargs="?", help="conversations.json or the export .zip")
    ap.add_argument("--dest", default=str(DEFAULT_DEST), help="output folder (default: vault/inbox/chats)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be written, write nothing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    if not args.source:
        ap.print_usage(sys.stderr)
        print("error: give the conversations.json or the export .zip", file=sys.stderr)
        return 2
    return run(Path(args.source), Path(args.dest), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
