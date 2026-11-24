# Memory

What a line of `vault/memory/` is, and how the repo keeps it honest.

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
