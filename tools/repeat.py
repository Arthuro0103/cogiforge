#!/usr/bin/env python3
"""repeat.py: was the user corrected AGAIN on something the memory already said? Stdlib only.

    python3 tools/repeat.py [--vault vault] [--corrections memory/observations.md] [--json] [--gate]
    python3 tools/repeat.py --selftest

Two inputs, both plain files in the vault, nothing else is read and nothing is written:
  memory       every dated entry (`YYYY-MM-DD | "what the user said" | where`, or `- YYYY-MM-DD: ...`) of the
               files directly under `memory/` (profile, patterns, decisions...), except the corrections file;
  corrections  the dated entries of the corrections file (default `memory/observations.md`, where Claude
               proposes what it saw). EVERY dated entry there counts as a correction: this tool does not guess
               which sentences are corrections, so keep in that file only what the user corrected.
For each correction it finds the memory entry that covers the most of its words (weighted by how rare each
word is in the memory) and counts it as a REPEAT only when that entry is older than the correction by more
than 3 days (a closer one is probably the same incident). The match is LEXICAL: a list of candidates for
the user's eye, never a verdict. A memory entry repeated twice, or once with a second correction within 3
days of it, is a candidate for a hard rule.
With no memory entry or no correction it prints NOT_VERIFIED and exits 3: "0 repeats" of nothing is not a result.
rc: 0 report · 1 --gate and there is a candidate (or --selftest failed) · 2 usage · 3 NOT_VERIFIED
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

THRESHOLD = 0.30      # share of the correction's word weight that the memory entry must cover
MIN_COMMON = 3        # fewer shared words than this is a loose word, not a match
NEAR_DAYS = 3         # a memory this close to the correction is probably the same incident
ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})\s*[|:]?\s*(.*)$")
STOP = set("""
the and for you your not that this with are was were has have had but can could would should will just
from into onto what when where which who how why about there their then than them they she him his her its
our out all any one more some very also only still like need want don didn doesn isn aren
""".split())


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def tokens(s: str) -> set[str]:
    """Words without accents or stopwords, cut to 5 letters (repo = repos, said = saids)."""
    return {t[:5] for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) >= 3 and t not in STOP}


def parse_entries(text: str) -> list[dict]:
    """Dated entries in order; an indented line under an entry belongs to it. A bad date is skipped."""
    out: list[dict] = []
    for line in text.split("\n"):
        m = ENTRY.match(line)
        if m:
            try:
                day = date.fromisoformat(m.group(1))
            except ValueError:
                out.append(None)  # type: ignore[arg-type]  # keeps continuation lines from joining the wrong entry
                continue
            out.append({"date": day, "text": m.group(2).strip()})
        elif out and out[-1] is not None and line.strip() and line[:1] in " \t":
            out[-1]["text"] += " " + line.strip()
    return [e for e in out if e is not None]


def idf_of(entries: list[dict]) -> dict[str, float]:
    df: dict[str, int] = defaultdict(int)
    for e in entries:
        for t in e["toks"]:
            df[t] += 1
    n = len(entries)
    return {t: math.log((n + 1) / (c + 0.5)) + 1 for t, c in df.items()}


def score(said: set[str], mem: set[str], idf: dict[str, float], unseen: float) -> float:
    """Share of the correction's weight that the memory entry covers (coverage of the SHORT text, not cosine)."""
    common = said & mem
    if len(common) < MIN_COMMON:
        return 0.0
    w = lambda t: idf.get(t, unseen)  # noqa: E731
    return sum(w(t) for t in common) / sum(w(t) for t in said)


def analyse(memory: list[dict], corrections: list[dict], threshold: float = THRESHOLD) -> dict:
    for e in memory + corrections:
        e["toks"] = tokens(e["text"])
    idf = idf_of(memory)
    unseen = max(idf.values(), default=1.0)
    repeats: dict[str, dict] = {}
    near: dict[str, int] = defaultdict(int)
    for c in corrections:
        ranked = sorted(((score(c["toks"], m["toks"], idf, unseen), k) for k, m in enumerate(memory)), reverse=True)
        for s, k in ranked:
            if s < threshold:
                break
            m = memory[k]
            if m["date"] >= c["date"]:
                continue  # a later memory cannot have been repeated
            key = f"{m['date']} {m['text'][:80]}"
            if (c["date"] - m["date"]).days <= NEAR_DAYS:
                near[key] += 1
            else:
                r = repeats.setdefault(key, {"n": 0, "dates": [], "said": []})
                r["n"] += 1
                r["dates"].append(c["date"].isoformat())
                if len(r["said"]) < 3:
                    r["said"].append(c["text"][:200])
            break  # only the best OLDER memory counts
    candidates = [k for k, r in repeats.items() if r["n"] >= 2]
    candidates += [k for k, r in repeats.items() if r["n"] == 1 and near.get(k) and k not in candidates]
    return {"memory": len(memory), "corrections": len(corrections), "repeats": repeats,
            "near": dict(near), "candidates": candidates}


def read_entries(path: Path) -> list[dict]:
    return parse_entries(path.read_text(encoding="utf-8"))


def load(vault: Path, corrections_file: Path) -> tuple[list[dict], list[dict]]:
    skip = corrections_file.resolve()
    memory: list[dict] = []
    for f in sorted((vault / "memory").glob("*.md")):
        if f.resolve() != skip:
            memory += read_entries(f)
    return memory, read_entries(corrections_file)


def print_report(r: dict) -> None:
    total = sum(x["n"] for x in r["repeats"].values())
    print(f"{r['memory']} memory entries · {r['corrections']} corrections · {total} repeats counted")
    for key, x in sorted(r["repeats"].items(), key=lambda kv: (-kv[1]["n"], kv[0])):
        print(f"{x['n']:>3}  {key}  (corrected again on {', '.join(x['dates'])})")
    print("\ncandidates for a hard rule (2+ repeats, or 1 repeat plus another correction within "
          f"{NEAR_DAYS} days of the memory, not counted):")
    for k in r["candidates"] or ["(none)"]:
        print(f"  - {k}" + (f"  [+{r['near'][k]} near]" if r["near"].get(k) else ""))
    print("\nWARNING: the match is LEXICAL. This is a list of candidates, not a verdict: "
          "read the correction against the memory before making a rule of it.")


def selftest() -> int:
    mem = ('# Patterns\n\n- 2026-01-01 | "never invent a link to a shop page before you opened it" | chat\n'
           '- 2026-01-02 | "keep the answers short and direct" | chat\n'
           '- 2026-03-01 | "always check the dishwasher filter weekly" | chat\n')
    obs = ('# Observations\n\n'
           '- 2026-02-10: you invented a link to a shop page again, open it before you link it\n'
           '- 2026-02-20: another invented link to a shop page, I said open it before you link it\n'
           '- 2026-02-25: the weather report was in celsius and I wanted fahrenheit\n'
           '- 2026-02-01: dishwasher filter check weekly, forgot it\n')
    results = []
    with tempfile.TemporaryDirectory() as d:
        v = Path(d)
        (v / "memory").mkdir()
        (v / "memory" / "patterns.md").write_text(mem, encoding="utf-8")
        (v / "memory" / "observations.md").write_text(obs, encoding="utf-8")
        memory, corr = load(v, v / "memory" / "observations.md")
        r = analyse(memory, corr)
        link = next((x for k, x in r["repeats"].items() if "shop page" in k), None)
        results.append(("a repeated rule is found twice", link is not None and link["n"] == 2))
        results.append(("an unrelated correction matches nothing", sum(x["n"] for x in r["repeats"].values()) == 2))
        results.append(("a later memory is not a repeat", not any("dishwasher" in k for k in r["repeats"])))
        results.append(("two repeats make a candidate", len(r["candidates"]) == 1))
        results.append(("the corrections file is not memory", len(memory) == 3))
        (v / "memory" / "observations.md").write_text("# nothing dated\n", encoding="utf-8")
        results.append(("no correction is NOT_VERIFIED", main(["--vault", str(v)]) == 3))
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    ok = all(ok for _, ok in results)
    print("selftest:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default=str(Path(__file__).resolve().parent.parent / "vault"))
    ap.add_argument("--corrections", default=None, help="file with the corrections (default: <vault>/memory/observations.md)")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true", help="exit 1 when there is a candidate for a hard rule")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not 0 < a.threshold <= 1:
        ap.error("--threshold must be above 0 and at most 1")
    vault = Path(a.vault)
    cfile = Path(a.corrections) if a.corrections else vault / "memory" / "observations.md"
    try:
        memory, corrections = load(vault, cfile)
    except (OSError, UnicodeDecodeError) as e:
        print(f"NOT_VERIFIED: could not read the memory or the corrections ({type(e).__name__}: {e}); nothing was compared.")
        return 3
    if not memory:
        print("NOT_VERIFIED: there is no dated entry under memory/, so nothing was compared (0 repeats of nothing is not a result).")
        return 3
    if not corrections:
        print(f"NOT_VERIFIED: {cfile} has no dated entry (a line that starts with YYYY-MM-DD), so no correction was checked.")
        return 3
    r = analyse(memory, corrections, a.threshold)
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
    else:
        print_report(r)
    return 1 if a.gate and r["candidates"] else 0


if __name__ == "__main__":
    sys.exit(main())
