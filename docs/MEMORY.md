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

## When a memory goes stale

A memory line that states a fact about a file or a state ages: the file it cites disappears or changes folder,
or changes so much that the sentence no longer holds. The next session obeys the old line anyway, and a line
marked "obsolete" that stays loaded is still obeyed. So the repo measures staleness and moves replaced lines out
of what loads. `python3 tools/stale.py` reports 5 signals for every entry of every memory file (team memory
included, `archive/` excluded):

| Signal | It means |
|---|---|
| `dead-path` | a path cited in the phrase or in `where` (in `backticks` or `[[wikilinks]]`, relative to `vault/`) does not exist, and no file with that name exists in the vault |
| `moved` | it does not exist, but a file with that name exists in another folder (the new path is shown) |
| `aged` | the cited file exists and had at least `--threshold` (default 3) commits after the entry date |
| `expired` | the entry has `stale_after:` in the past; a note in `vault/notes/` with `stale_after:` in its frontmatter counts too |
| `superseded` | the entry has `superseded_by:` and is still in a loaded file |

Two optional final fields on an entry say it by hand:

```
2026-02-01 | "the plan lives in docs/plan.md" | inbox/chats/plan.md | stale_after: 2026-12-01
2026-02-01 | "use rule A" | inbox/chats/rules.md | superseded_by: 2026-09-09
```

The field names come from the Open Knowledge Format (OKF); this repo does not claim any version of it.

The tool measures and does not decide: it exits 0 with a report, `--gate` exits 1 on any finding, and a
file it cannot read is `NOT_VERIFIED` (exit 3), never a pass. Without git the `aged` signal is `NOT_VERIFIED`
and the other four still run. `cf-close-session` runs it and shows the findings; nothing in the memory is changed
without the user's "yes". A `superseded_by:` entry leaves the loaded file first when you run
`python3 tools/cool.py memory/<file>.md`, whatever its date and `--keep`.
