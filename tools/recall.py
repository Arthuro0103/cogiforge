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

Known limit: a negation still matches ("not 6 am" contains the term "6 am"), so a wrong answer that quotes the
right term passes. Terms are refused if they are shorter than 3 characters or appear in the question itself.

--static (default, no model) classifies every `recall` item:
  loaded       its terms are in the files a session loads (core/budget.py `loaded_files`, taken together: with
               `"all": true` the terms may be in different loaded files; in team mode the memory of
               vault/people/<handle>/memory/ counts as loaded too)
  archived     its terms are only in memory/archive/<name>.md AND the loaded file memory/<name>.md keeps the
               pointer line that cool.py leaves behind, so a session knows where to look
  MISSING      anywhere else, or archived with no pointer (problem)
  contaminated its terms are also in CLAUDE.md, AGENTS.md or vault/CLAUDE.md: the test would measure the rules
               file, not the memory (problem)
and it reports a BUDGET problem when core/budget.py says a ceiling is crossed. A `positive-control` must be
`loaded`, in a MEMORY file (vault/memory/*.md, vault/people/*/memory/*.md) and in no rules file, or the
problem is CONTROL-NOT-IN-MEMORY. rc 0 no problem, 1 a problem.

--run "CMD" runs only if --static passed. CMD is split with shlex (no shell), gets the prompt on stdin and has
600 s, with the repo root as its working directory. Only `loaded` items are asked: an `archived` one is not
(the prompt forbids reading files, which is what lets the positive-control prove the memory was loaded). "I don't know" counts only at the START of an answer and beats the terms. A wrong positive-control is
NOT_VERIFIED, and so is a missing answer (the format was not followed), a failing command or output that is not
UTF-8; a NOT_VERIFIED run prints no score and logs `recall_ok: null`. A wrong recall or an invented negative-control is DEGRADED; all right is OK. --log appends one
JSON line to vault/memory/recall-history.jsonl.
rc: 0 OK / static clean · 1 problem or DEGRADED · 2 usage or invalid bank · 3 NOT_VERIFIED (no bank, no
recall item, no positive-control, the command failed, or a positive-control was missed)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import budget  # noqa: E402

IS_WINDOWS = os.name == "nt"

ID_OK = re.compile(r"^[A-Za-z0-9_-]+$")
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
        if not isinstance(iid, str) or not ID_OK.match(iid):
            raise BankError(f"item {k}: the id must match [A-Za-z0-9_-]+")
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
            q = norm(it["question"])
            for t in acc:
                if len(norm(t).strip()) < 3:
                    raise BankError(f"{iid}: the term {t!r} is shorter than 3 characters")
                if has_term(q, norm(t)):
                    raise BankError(f"{iid}: the term {t!r} is in the question itself, so the answer would echo it")
        if "all" in it and not isinstance(it["all"], bool):
            raise BankError(f"{iid}: `all` must be true or false")
    return items


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def live_text(text: str) -> str:
    """The text without HTML comments and code (a link inside them is not a pointer a session sees)."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"^(```|~~~).*?^\1[^\n]*$", "", text, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", text)


def has_pointer(loaded_text: str, stem: str) -> bool:
    """The line cool.py leaves behind: a link to memory/archive/<stem> (with or without `.md`)."""
    return re.search(r"\[\[memory/archive/" + re.escape(stem) + r"(?:\.md)?[|\]]", live_text(loaded_text)) is not None


def team_memory(vault: Path) -> list[Path]:
    return sorted((vault / "people").glob("*/memory/*.md"))


def classify(item: dict, vault: Path, root: Path) -> str:
    # a session loads all these files together, so `all` is judged on their union
    # team mode: people/<handle>/memory/ is the memory of whoever is talking, so it is loaded like the three files
    if found("\n".join(read(p) for p in budget.loaded_files(vault, root) + team_memory(vault)), item):
        return "loaded"
    if item["type"] == "recall":
        for stem in budget.MEMORY:
            if found(read(vault / "memory" / "archive" / f"{stem}.md"), item) and \
                    has_pointer(read(vault / "memory" / f"{stem}.md"), stem):
                return "archived"
    return "MISSING"


def contaminated(item: dict, vault: Path, root: Path) -> bool:
    return found("\n".join(read(root / n) for n in RULES_FILES) + "\n" + read(vault / "CLAUDE.md"), item)


def memory_files(vault: Path) -> list[Path]:
    return sorted((vault / "memory").glob("*.md")) + team_memory(vault)


def static(items: list[dict], vault: Path, root: Path) -> tuple[list[str], list[str], dict]:
    """(one line per item, problems, state by id)."""
    lines, problems, states = [], [], {}
    for it in items:
        if it["type"] == "negative-control":
            lines.append(f"{it['id']:<24}negative-control  (graded only with --run)")
            continue
        state = classify(it, vault, root)
        if it["type"] == "recall" and contaminated(it, vault, root):
            state = "contaminated"
        if it["type"] == "positive-control" and state == "loaded" and (
                not found("\n".join(read(p) for p in memory_files(vault)), it) or contaminated(it, vault, root)):
            state = "CONTROL-NOT-IN-MEMORY"
        states[it["id"]] = state
        if state in ("MISSING", "contaminated", "CONTROL-NOT-IN-MEMORY"):
            problems.append(f"{it['id']}: {state}")
        lines.append(f"{it['id']:<24}{it['type']:<17} {state}")
    m = budget.measure(vault, root)
    for over in budget.verdict(m):
        problems.append(f"BUDGET: {over}")
    return lines, problems, states


UNKNOWN = re.compile(r"i (?:don'?t|do not) know(?![a-z0-9])")


def starts_unknown(answer: str) -> bool:
    """"I don't know" at the START of the answer: after one list marker (`3.`) and markdown marks (`>`, `*`, `_`),
    nothing else (digits, quotes or words before it make it a real answer)."""
    a = re.sub(r"^[\s>*_]+", "", norm(answer))
    a = re.sub(r"^\d+[.)]\s+", "", a, count=1)
    a = re.sub(r"^[\s>*_]+", "", a)
    return UNKNOWN.match(a) is not None


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


def parse_answers(text: str, n: int) -> list[str | None]:
    """In order: an answer starts only at the line `N.` or `N)` where N is the NEXT number expected; any other line
    (a repeated `1.`, `1.5 h`, `0.`, `9.`) continues the current answer. None where an answer never came."""
    out: list[str | None] = [None] * n
    cur = None
    for ln in text.splitlines():
        m = re.match(r"^\s*(\d+)[.)]\s*(.*)$", ln)
        nxt = 0 if cur is None else cur + 1
        if m and nxt < n and int(m.group(1)) == nxt + 1:
            cur = nxt
            out[cur] = m.group(2).strip()
        elif cur is not None and ln.strip():
            out[cur] = (out[cur] + " " + ln.strip()).strip()
    return [a if a else None for a in out]


def not_verified(reason: str) -> dict:
    return {"status": "NOT_VERIFIED", "reason": reason, "rc": 3, "recall_ok": None, "recall_total": None,
            "missed": None, "invented": None, "per_item": {}}


def verdict(items: list[dict], answers: list[str | None]) -> dict:
    for k, a in enumerate(answers, 1):
        if a is None:
            return not_verified(f"the agent did not answer item {k}; the format was not followed")
    res = {it["id"]: grade(a, it) for it, a in zip(items, answers)}
    kind = lambda t: [it for it in items if it["type"] == t]  # noqa: E731
    rec, pos, neg = kind("recall"), kind("positive-control"), kind("negative-control")
    if any(res[i["id"]] != "ok" for i in pos):
        return not_verified("a positive-control was missed: the agent did not read the memory")
    if not rec:
        return not_verified("no recall item was asked (all are archived), so nothing was measured")
    ok = sum(res[i["id"]] == "ok" for i in rec)
    missed, invented = [i["id"] for i in rec if res[i["id"]] != "ok"], [i["id"] for i in neg if res[i["id"]] != "ok"]
    good = not missed and not invented
    return {"status": "OK" if good else "DEGRADED", "reason": None, "rc": 0 if good else 1, "recall_ok": ok,
            "recall_total": len(rec), "missed": missed, "invented": invented, "per_item": res}


def run_model(argv: list[str], prompt: str, cwd: Path, timeout: float = TIMEOUT) -> str:
    """Run the command in its own process group; on a timeout kill the whole group (no grandchild is left)."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                            start_new_session=not IS_WINDOWS)
    try:
        out, err = proc.communicate(prompt.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        if IS_WINDOWS:
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
        proc.communicate()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"the command exited {proc.returncode}: {err.decode('utf-8', 'replace').strip()[:300]}")
    return out.decode("utf-8")  # UnicodeDecodeError: the output is not text, so it is not an answer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", help="the repo root with CLAUDE.md and AGENTS.md (default: the vault's parent folder)")
    ap.add_argument("--bank", help="the question bank (default: <vault>/memory/recall.json)")
    ap.add_argument("--static", action="store_true", help="check the disk only, no model (the default)")
    ap.add_argument("--run", metavar="CMD", help="ask a model through CMD (prompt on stdin), after --static passes")
    ap.add_argument("--timeout", type=float, default=TIMEOUT, help=argparse.SUPPRESS)
    ap.add_argument("--log", action="store_true", help="with --run: append a line to <vault>/memory/recall-history.jsonl")
    a = ap.parse_args(argv)
    argv_cmd = None
    if a.run is not None:
        try:
            argv_cmd = shlex.split(a.run)
        except ValueError as e:
            print(f"usage: --run could not be split into a command ({e})", file=sys.stderr)
            return 2
        if not argv_cmd:
            print("usage: --run needs a command", file=sys.stderr)
            return 2
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
    lines, problems, states = static(items, vault, root)
    print("\n".join(lines))
    print(f"static: {len(items)} item(s), {len(problems)} problem(s)")
    for p in problems:
        print(f"PROBLEM: {p}")
    if not a.run:
        return 1 if problems else 0
    if problems:
        print("--run skipped: fix the static problems first, or the answers would not mean anything.")
        return 1
    asked = [it for it in items if states.get(it["id"]) != "archived"]
    archived = [it["id"] for it in items if states.get(it["id"]) == "archived"]
    if archived:
        print(f"archived: not asked (found on demand; --static checked the pointer): {', '.join(archived)}")
    try:
        answers = parse_answers(run_model(argv_cmd, build_prompt(asked), root, a.timeout), len(asked))
        v = verdict(asked, answers)
    except (RuntimeError, OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as e:
        v = not_verified(f"the command did not answer ({type(e).__name__}: {e})")
    if v["status"] == "NOT_VERIFIED":
        print(f"NOT_VERIFIED: {v['reason']} (score not valid)")
    else:
        print(f"{v['status']}: recall {v['recall_ok']}/{v['recall_total']}, missed {v['missed']}, invented {v['invented']}")
    if a.log:
        rec = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "command": a.run,
               "recall_ok": v["recall_ok"], "recall_total": v["recall_total"], "missed": v["missed"],
               "invented": v["invented"], "verdict": v["status"]}
        with (vault / "memory" / "recall-history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return v["rc"]


if __name__ == "__main__":
    sys.exit(main())
