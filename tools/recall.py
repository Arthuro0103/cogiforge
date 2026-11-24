#!/usr/bin/env python3
"""recall.py: does a NEW session still find what was written in the memory? Stdlib only.

    python3 tools/recall.py [--static] [--vault vault] [--root DIR] [--bank vault/memory/recall.json]
    python3 tools/recall.py --run "claude -p" [--log]      ask a model the bank's questions and grade the answers

Why it exists: the memory files (profile, patterns, decisions) load in every session, and tools/cool.py moves
the older entries to memory/archive/, which loads only on demand. Nothing measured whether a fresh session
still ANSWERS from what was written. In the vault this comes from, on 2026-09-22 a new session answered "I do
not know" to 3 of 3 questions whose hook had been cut off the end of an oversized index.

The bank (`vault/memory/recall.json`, template in `recall.example.json`) is a list of items:
  recall            a fact the memory must still give. `accept` lists terms; any one is enough, or all of them
                    with `"all": true`. A term counts only as a whole word, ignoring case and accents.
  positive-control  a fact that is surely in the loaded memory. If the model misses it, it did not read the
                    memory, and no number from that run means anything.
  negative-control  a question the memory cannot answer. The only right answer is "I don't know".

--static (default, no model) classifies every `recall` item:
  loaded       its terms are in a file a session loads (core/budget.py `loaded_files`)
  archived     its terms are only in memory/archive/<name>.md AND the loaded file memory/<name>.md keeps the
               pointer line that cool.py leaves behind, so a session knows where to look
  MISSING      anywhere else, or archived with no pointer (problem)
  contaminated its terms are also in CLAUDE.md, AGENTS.md or vault/CLAUDE.md: the test would measure the rules
               file, not the memory (problem)
and it reports a BUDGET problem when core/budget.py says a ceiling is crossed. A `positive-control` must be
`loaded`. rc 0 no problem, 1 a problem.

--run "CMD" runs only if --static passed. CMD is split with shlex (no shell), gets the prompt on stdin and has
600 s. "I don't know" counts only at the START of an answer and beats the terms. A wrong positive-control is
NOT_VERIFIED; a wrong recall or an invented negative-control is DEGRADED; all right is OK. --log appends one
JSON line to vault/memory/recall-history.jsonl.
rc: 0 OK / static clean · 1 problem or DEGRADED · 2 usage or invalid bank · 3 NOT_VERIFIED (no bank, no
recall item, no positive-control, the command failed, or a positive-control was missed)
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import budget  # noqa: E402

TYPES = ("recall", "positive-control", "negative-control")
TIMEOUT = 600
HOW_TO_CREATE = ("copy vault/memory/recall.example.json to vault/memory/recall.json and replace the examples with "
                 "facts that really are in your memory (at least one `recall` and one `positive-control`)")
RULES_FILES = ("CLAUDE.md", "AGENTS.md")


class BankError(ValueError):
    pass


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("’", "'"))
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn").lower())


def has_term(text_norm: str, term_norm: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term_norm) + r"(?![a-z0-9])", text_norm) is not None


def found(text: str, item: dict) -> bool:
    """Do the terms of `accept` appear in `text`? Every one with `all`, else any one."""
    n = norm(text)
    hits = [has_term(n, norm(t)) for t in item["accept"]]
    return all(hits) if item.get("all") else any(hits)


def load_bank(path: Path) -> list[dict]:
    """The items, or BankError (invalid) / FileNotFoundError (absent)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BankError(f"cannot read the bank {path}: {type(e).__name__}") from e
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise BankError('the bank must be {"items": [...]}')
    seen = set()
    for k, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise BankError(f"item {k} is not an object")
        iid = it.get("id")
        if not isinstance(iid, str) or not iid.strip():
            raise BankError(f"item {k} has no id")
        if iid in seen:
            raise BankError(f"repeated id: {iid}")
        seen.add(iid)
        if it.get("type") not in TYPES:
            raise BankError(f"{iid}: invalid type {it.get('type')!r} (use {', '.join(TYPES)})")
        if not isinstance(it.get("question"), str) or not it["question"].strip():
            raise BankError(f"{iid}: no question")
        if it["type"] != "negative-control":
            acc = it.get("accept")
            if not isinstance(acc, list) or not acc or not all(isinstance(t, str) and norm(t).strip() for t in acc):
                raise BankError(f"{iid}: `accept` must be a non-empty list of terms")
        if "all" in it and not isinstance(it["all"], bool):
            raise BankError(f"{iid}: `all` must be true or false")
    return items


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def has_pointer(loaded_text: str, stem: str) -> bool:
    """The line cool.py leaves behind: a link to memory/archive/<stem>."""
    return re.search(r"\[\[memory/archive/" + re.escape(stem) + r"[|\]]", loaded_text) is not None


def classify(item: dict, vault: Path, root: Path) -> str:
    loaded = [read(p) for p in budget.loaded_files(vault, root)]
    if any(found(t, item) for t in loaded):
        return "loaded"
    if item["type"] == "recall":
        for stem in budget.MEMORY:
            if found(read(vault / "memory" / "archive" / f"{stem}.md"), item) and \
                    has_pointer(read(vault / "memory" / f"{stem}.md"), stem):
                return "archived"
    return "MISSING"


def contaminated(item: dict, vault: Path, root: Path) -> bool:
    rules = [read(root / n) for n in RULES_FILES] + [read(vault / "CLAUDE.md")]
    return any(found(t, item) for t in rules)


def static(items: list[dict], vault: Path, root: Path) -> tuple[list[str], list[str]]:
    """(one line per item, problems)."""
    lines, problems = [], []
    for it in items:
        if it["type"] == "negative-control":
            lines.append(f"{it['id']:<24}negative-control  (graded only with --run)")
            continue
        state = classify(it, vault, root)
        if it["type"] == "recall" and contaminated(it, vault, root):
            state = "contaminated"
        if state in ("MISSING", "contaminated"):
            problems.append(f"{it['id']}: {state}")
        lines.append(f"{it['id']:<24}{it['type']:<17} {state}")
    m = budget.measure(vault, root)
    for over in budget.verdict(m):
        problems.append(f"BUDGET: {over}")
    return lines, problems


def starts_unknown(answer: str) -> bool:
    """"I don't know" (any case, apostrophe optional) at the START, after numbering, quotes and punctuation."""
    a = re.sub(r"^[\s\d.)\-*\"'`(]+", "", norm(answer))
    return re.match(r"i don'?t know\b", a) is not None


def grade(answer: str, item: dict) -> str:
    """ok | wrong | unknown. "I don't know" is tested BEFORE the terms."""
    unknown = starts_unknown(answer)
    if item["type"] == "negative-control":
        return "ok" if unknown else "wrong"
    if unknown:
        return "unknown"
    return "ok" if found(answer, item) else "wrong"


def build_prompt(items: list[dict]) -> str:
    qs = "\n".join(f"{i}. {it['question']}" for i, it in enumerate(items, 1))
    return ("Answer ONLY from the memory already loaded in this session. Do not read files and do not use tools. "
            "Answer each question by its number, one line each, as `N. answer`, at most 20 words. "
            "If the answer is not in your memory, start that answer with exactly `I DON'T KNOW` and do not guess.\n\n" + qs)


def parse_answers(text: str, n: int) -> list[str]:
    out, cur = [""] * n, None
    for ln in text.splitlines():
        m = re.match(r"^\s*(\d+)[.)]\s*(.*)$", ln)
        if m and 1 <= int(m.group(1)) <= n:
            cur = int(m.group(1)) - 1
            out[cur] = m.group(2).strip()
        elif cur is not None and ln.strip():
            out[cur] += " " + ln.strip()
    return out


def verdict(items: list[dict], answers: list[str]) -> dict:
    res = {it["id"]: grade(a, it) for it, a in zip(items, answers)}
    kind = lambda t: [it for it in items if it["type"] == t]  # noqa: E731
    rec, pos, neg = kind("recall"), kind("positive-control"), kind("negative-control")
    ok = sum(res[i["id"]] == "ok" for i in rec)
    base = {"recall_ok": ok, "recall_total": len(rec), "missed": [i["id"] for i in rec if res[i["id"]] != "ok"],
            "invented": [i["id"] for i in neg if res[i["id"]] != "ok"], "per_item": res}
    if any(res[i["id"]] != "ok" for i in pos):
        return {**base, "status": "NOT_VERIFIED", "reason": "a positive-control was missed: the agent did not read the memory", "rc": 3}
    good = ok == len(rec) and not base["invented"]
    return {**base, "status": "OK" if good else "DEGRADED", "reason": None, "rc": 0 if good else 1}


def run_model(cmd: str, prompt: str) -> str:
    argv = shlex.split(cmd)
    if not argv:
        raise RuntimeError("the command is empty")
    p = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=TIMEOUT)
    if p.returncode != 0:
        raise RuntimeError(f"the command exited {p.returncode}: {p.stderr.strip()[:300]}")
    return p.stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", help="the repo root with CLAUDE.md and AGENTS.md (default: the vault's parent folder)")
    ap.add_argument("--bank", help="the question bank (default: <vault>/memory/recall.json)")
    ap.add_argument("--static", action="store_true", help="check the disk only, no model (the default)")
    ap.add_argument("--run", metavar="CMD", help="ask a model through CMD (prompt on stdin), after --static passes")
    ap.add_argument("--log", action="store_true", help="with --run: append a line to <vault>/memory/recall-history.jsonl")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    root = Path(a.root).resolve() if a.root else vault.parent
    bank = Path(a.bank) if a.bank else vault / "memory" / "recall.json"
    try:
        items = load_bank(bank)
    except FileNotFoundError:
        print(f"NOT_VERIFIED: there is no bank at {bank}, so nothing was measured. To create it: {HOW_TO_CREATE}.")
        return 3
    except BankError as e:
        print(f"invalid bank: {e}", file=sys.stderr)
        return 2
    if not any(i["type"] == "recall" for i in items) or not any(i["type"] == "positive-control" for i in items):
        print(f"NOT_VERIFIED: the bank needs at least one `recall` and one `positive-control` item (without the "
              f"control, a miss cannot tell a lost memory from an agent that never read it). To fix it: {HOW_TO_CREATE}.")
        return 3
    if not vault.is_dir():
        print(f"NOT_VERIFIED: the vault '{vault}' does not exist.")
        return 3
    lines, problems = static(items, vault, root)
    print("\n".join(lines))
    print(f"static: {len(items)} item(s), {len(problems)} problem(s)")
    for p in problems:
        print(f"PROBLEM: {p}")
    if not a.run:
        return 1 if problems else 0
    if problems:
        print("--run skipped: fix the static problems first, or the answers would not mean anything.")
        return 1
    try:
        answers = parse_answers(run_model(a.run, build_prompt(items)), len(items))
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print(f"NOT_VERIFIED: the command did not answer ({type(e).__name__}: {e}).")
        return 3
    v = verdict(items, answers)
    print(f"{v['status']}: recall {v['recall_ok']}/{v['recall_total']}, missed {v['missed']}, invented {v['invented']}"
          + (f" ({v['reason']})" if v["reason"] else ""))
    if a.log:
        rec = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "command": a.run,
               "recall_ok": v["recall_ok"], "recall_total": v["recall_total"], "missed": v["missed"],
               "invented": v["invented"], "verdict": v["status"]}
        with (vault / "memory" / "recall-history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return v["rc"]


if __name__ == "__main__":
    sys.exit(main())
