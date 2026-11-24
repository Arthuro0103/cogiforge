# How the memory works in this repo

## The files

Three files in `vault/memory/` load at the start of every session, so they are the memory a new session has:

| file | what goes in it |
|---|---|
| `profile.md` | who the user says they are |
| `patterns.md` | habits and blockers the user recognized themselves |
| `decisions.md` | what the user decided, and why |

Only the user's own words go in. The agent proposes in `memory/observations.md`; a line enters one of the three
files only after the user's "yes".

Each entry is one line:

    YYYY-MM-DD | "verbatim phrase" | where it was said

The date comes first because `tools/cool.py` reads it.

## Cooling: when a file gets too big

A file that every session loads can only grow until it crosses the ceiling in `core/budget.py`. Then
`python3 tools/cool.py memory/<file>.md --keep 40` plans a move (and `--apply`, with the user's yes, does it):
the older dated entries go, word for word, to `memory/archive/<file>.md`, and one pointer line stays behind in
the loaded file. The archive loads only on demand, so a session finds an archived fact only if it follows the
pointer.

## Does a new session still find it?

Cooling saves bytes and can lose answers. `tools/recall.py` measures that against a small bank of questions in
`vault/memory/recall.json` (copy `vault/memory/recall.example.json` and replace the examples with facts that are
really in your memory). The bank has three kinds of item: `recall` (a fact the memory must still give),
`positive-control` (a fact surely in the loaded files: if the model misses it, it never read the memory) and
`negative-control` (a question the memory cannot answer: the only right answer is "I don't know").

- `python3 tools/recall.py` (same as `--static`) uses no model. For each `recall` item it says `loaded`,
  `archived` (the fact is in the archive AND the loaded file keeps cool.py's pointer) or `MISSING`. It also flags
  an item `contaminated` when its terms are in `CLAUDE.md`, `AGENTS.md` or `vault/CLAUDE.md` (the test would
  measure the rules file, not the memory) and a `BUDGET` problem when a ceiling is crossed.
- `python3 tools/recall.py --run "claude -p" --log` runs only if the static check passed. It sends the numbered
  questions on stdin, grades the answers and appends one line to `vault/memory/recall-history.jsonl`. `OK`, or
  `DEGRADED` (a recall missed, or a negative-control that invented an answer), or `NOT_VERIFIED` (a
  positive-control was missed, so the number says nothing). Another CLI can take the place of `claude -p`:
  [VERIFY] that it reads the prompt from stdin and prints the answer on stdout; this was not tested here.
