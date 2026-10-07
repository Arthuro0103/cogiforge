---
name: adopt
description: Applies the cogiforge to an Obsidian vault the person ALREADY has, in place, copying nothing into an inbox. Runs tools/adopt.py as a dry run, reads the plan in plain words (areas inferred from their folders, what would be installed, the debt measured today, and that the hook only judges notes in the commit), asks "want to apply?", and only then runs it with --apply --yes. It invents no link and states nothing about the person. TRIGGERS - "/adopt <vault>", "use this on my existing vault", "I already have an Obsidian vault", "start from my current notes", "I do not want to start from zero", "move from my old tool without copying". Do NOT trigger to bring loose files or another folder INTO this vault (that is import-knowledge), to capture one idea, to open or close a session, nor to fix the old debt note by note without being asked.
---

# adopt: put the gate on the vault you already have

## Why it exists

Starting from zero means losing a vault that already works; migrating means copying thousands of notes into an
inbox that nobody triages. `tools/adopt.py` does neither: it leaves every note where it is, measures how much
debt already exists, installs the gate, and promises one thing: **from now on, new notes in a commit are checked,
and the old ones are not touched.**

## The rules

1. **No vault path, no run.** Ask which folder is the vault. Never guess a path and never search the disk for one.
2. **Dry run first, always.** `python3 tools/adopt.py <vault>` writes nothing. Do not run `--apply` before the user has seen the plan.
3. **Read the plan before saying anything.** Every statement points to a line of the output. If you did not read it, you do not claim it.
4. **Say what is pending first.** Not a git repository (the tool never runs `git init`; tell the user to run it themselves and try again), a CONFLICT (an existing file is kept as it is), skipped notes (iCloud placeholders not downloaded, unreadable, symlinks: they were NOT measured, which is not the same as fine), or "nothing to adopt". A DIFFERENT `.githooks/pre-commit` already in the vault is code from someone else that would run on every commit: the tool refuses to activate it and applies nothing. Show the user the lines the plan prints, tell them to read that hook and decide; never delete, replace or activate it for them.
   Also read the full hook text the plan prints and tell the user it will run on every commit.
5. **Ask, then apply.** Only after a clear "yes" to "do you want to apply this?" run `python3 tools/adopt.py <vault> --apply --yes`. A "maybe" or silence is a no.
6. **The tool writes, you do not.** Do not edit the user's notes, `areas.txt`, hooks or baseline by hand. Never touch an existing note.
7. **No invented links, nothing about the person.** Do not propose links to lower the debt unless the user asks and you can point at the sentence that justifies each one. Do not infer who they are from their folder names.
8. **Talk to the user in the language they write in.** Fixed tokens (paths, `areas.txt`, rc codes) stay as they are.

## The steps

### 1. Dry run (you)

```bash
python3 tools/adopt.py <vault>          # the plan; writes nothing
python3 tools/adopt.py <vault> --json   # same data, for you to read
```

### 2. Explain the plan in plain words (you), in at most 8 lines

1. The areas it found (the proposed `areas.txt`), and that the user can change them later.
2. What would be created, and what already exists and will be kept.
3. The debt today, as numbers: orphan notes, dead links, notes without `area:`. It is saved as `.cogiforge/baseline.json`.
4. The warning, literally: the hook only judges the notes in the commit, so the old debt blocks nobody. It only stops new orphans, dead links and personal data.
5. Anything pending (rule 4).

### 3. Ask

"Do you want to apply this?" One question, nothing else in the message.

### 4. Apply (you, only after yes)

```bash
python3 tools/adopt.py <vault> --apply --yes
```

Read its output and report what was written. Exit codes: `0` ok · `1` something pending · `2` usage or no confirmation · `3` vault unreadable.
Suggest a test: add a note with no link and run `git commit`; the hook should block it. Commit nothing yourself unless asked.

## Never

- Run `git init`, `--no-verify`, or `--apply` before the plan was read and confirmed.
- Overwrite or edit an existing note or config file, or activate a hook you did not generate.
- Call a vault "fine" when notes were skipped, or when it was empty ("nothing to adopt" is not OK).
