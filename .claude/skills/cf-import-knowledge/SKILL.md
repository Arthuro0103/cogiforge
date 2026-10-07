---
name: cf-import-knowledge
description: Brings an existing knowledge base (another vault, a folder of notes, a wiki export, loose documents) into the workbench. Runs tools/import.py, reads the report it writes, and then helps triage the imported inbox into vault/notes/ one batch at a time, following "the target comes first": a named target and a real link in the body for every note that moves. It proposes, the user approves; it invents no link and states nothing about the user. TRIGGERS - "/cf-import-knowledge <folder>", "import my old notes", "bring my wiki into the vault", "I have a folder of documents", "triage what was imported". Do NOT trigger to capture one loose idea (put it in vault/inbox/), to open or close a session, nor to rewrite notes that are already in vault/notes/.
---

# cf-import-knowledge: bring it in whole, then decide note by note

## Why it exists

A team, a school or a person usually arrives with a base that already exists. Copying it into `notes/`
would fill the vault with notes that link to nothing and serve nothing; leaving it outside means it is
never used. The path here has two separate steps: **copy and convert** (mechanical, a script does it, nothing
is lost) and **triage** (a decision, the user makes it). This skill drives both and never mixes them.

## The rules

1. **No source folder, no run.** Ask which folder. Never guess a path and never search the disk for one.
2. **The tool copies, you do not.** Run `tools/import.py`; do not copy, rename or convert files by hand. The original is never touched.
3. **Read the report before saying anything.** Every statement about what happened points to a line of `_import-report.md`. If you did not read it, you do not claim it.
4. **A leak is the first thing you report.** If the report has a WARNING about personal data, say it before anything else: the pre-commit hook will block the commit until the listed `file:line:type` are cleaned. Never print the data itself, and never edit the user's content to clean it without asking.
5. **Unconverted is not lost.** Files in `_unconverted/` are listed with a reason. Say how many there are and what unblocks them (usually `python3 -m pip install docling`, then run the same command again); do not try to read a binary file yourself.
6. **Propose, the user approves.** Nothing moves out of the inbox without a "yes" for that batch.
7. **No invented links, nothing about the user.** A link is created only if the connection is real and you can point at the sentence that justifies it. You do not write facts about the user; at most you propose them in `vault/memory/observations.md`, and they only enter `vault/memory/` with the user's "yes" and their own words.
8. **Talk to the user in the language they write in.** Fixed tokens (paths, frontmatter keys, the report's own words) stay as they are.

## The steps

### 1. Run the tool (you)

```bash
python3 tools/import.py <SRC> --dry-run           # plan first: prints the report, writes nothing
python3 tools/import.py <SRC>                     # copy and convert into vault/inbox/imported/<name>
python3 tools/import.py <SRC> --person <HANDLE>   # into that person's inbox (vault/people/<HANDLE>/ must exist)
```

Start with `--dry-run` when the source is large or the user is unsure. The result is the same folder
structure, markdown where it could be converted, and `_import-report.md` at the destination.

### 2. Read the report (you)

Open `<dest>/_import-report.md` and tell the user, in at most 8 lines: how many files were in the source and
how the count closed (converted, copied, unchanged, ignored, not converted, skipped), the leak WARNING first
if there is one, the name collisions, and the skipped files with their reasons (an iCloud placeholder that is not
downloaded needs the user to download it, then run again).

Exit codes: `0` ok · `1` something needs a look (not converted, skipped, or a leak; information, not an error) ·
`2` usage error · `3` source unreadable. "nothing to import" means the source had no importable file: say so, never call it a success.

### 3. Triage the inbox (you propose, they approve)

Work in batches of at most 10 notes, starting with the folder the user points at.

For each note, read it and propose **one** of the five targets from `vault/CLAUDE.md`:

| target | meaning | what moves |
|---|---|---|
| `project::<name>` | it feeds a project that already exists | the note goes to `notes/<area>/`, links to the project root in its body, and the project file changes in the same commit |
| `article::` | it belongs to a piece of writing | link to it from that piece |
| `question::` | it answers something the user asked | the answer goes where the question lives |
| `task::` | it implies work | a task in `vault/tasks/` with a link to the project root |
| `none` | nothing to do with it now | it stays in the inbox, with the date |

`none` is a legitimate answer. Present each batch as a table (note, proposed target, the sentence that
justifies the link, the area) and ask for approval of the batch, line by line if the user wants.

### 4. Apply only what was approved (you)

- Move with the frontmatter `area:` that matches the folder (`vault/areas.txt`), a title that is a statement of up to 10 words, and **the link in the body**, in the middle of the argument, never in a `## Connections` block at the bottom.
- Wikilinks inherited from the old base may be dead here: do not "fix" them by guessing. Either drop the brackets and say so, or ask.
- Run `python3 core/gate.py --vault vault` and `python3 core/ring.py --vault vault --gate` and read the output. Then `python3 tools/hub.py` if a project root gained notes.
- Commit only if the user says so, and never push.

## Never

- Copy, convert or delete files outside `tools/import.py`, or delete the source.
- Move a note to `notes/` without a named target and a real link in the body.
- Hide or shorten a leak list, or print the data it points at.
- Declare the import "done" while the report lists files that were not converted, without saying so.
