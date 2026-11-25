---
name: cf-adopt
description: Puts the Cogiforge commit gate on an Obsidian vault the person ALREADY has, in place, copying no notes - dry-runs adopt.py, explains the plan and the debt in plain words, applies only after a clear yes. TRIGGERS - "I already have an Obsidian vault", "start from my current notes". Do NOT trigger to make a new workbench (cf-new-workbench), nor to import loose files.
---

# cf-adopt: put the gate on the vault you already have

## Why it exists

Starting from zero means losing a vault that already works; migrating means copying thousands of notes into an
inbox that nobody triages. `tools/adopt.py` does neither: it leaves every note where it is, measures how much
debt already exists, installs the gate, and promises one thing: **from now on, new notes in a commit are checked,
and the old ones are not touched.**

## Why `~/.cogiforge`

The git hook needs a fixed address for Cogiforge, and the plugin carries only instructions (Markdown), no code. So this skill downloads Cogiforge 0.1.1 from GitHub, pinned to commit `1f0d9cc38ead38801fc3b2153e1f90f952628eb6` (tag `v0.1.1`), into `~/.cogiforge`, and checks that hash before it runs anything from the download. Never run anything from a download that failed the check. `adopt.py` is always run from `~/.cogiforge`: it records its own folder as `cogiforge.home` in the vault's local git config. It needs `git` and an internet connection.

## The rules

1. **No vault path, no run.** Ask which folder is the vault. Never guess a path and never search the disk for one. Use it as an ABSOLUTE path between SINGLE quotes, with `~` expanded by you (iCloud paths have spaces, and single quotes keep `$` and backticks in a folder name from running). If the path contains a single quote, ask the person to rename the folder or give another path (same rule as cf-new-workbench).
2. **Dry run first, always.** `python3 ~/.cogiforge/tools/adopt.py '/absolute/path/to/vault'` writes nothing. Do not run `--apply` before the user has seen the plan.
3. **Read the plan before saying anything.** Every statement points to a line of the output. If you did not read it, you do not claim it.
4. **Say what is pending first.** Not a git repository (the tool never runs `git init`; tell the user to run it themselves and try again), a CONFLICT (an existing file is kept as it is), skipped notes (iCloud placeholders not downloaded, unreadable, symlinks: they were NOT measured, which is not the same as fine), or "nothing to adopt". A DIFFERENT `.git/hooks/pre-commit` (or any other hook in `.git/hooks`) is code that already runs on git operations: the tool never overwrites nor chains it and applies nothing. Show the user the lines the plan prints, tell them to read that hook and decide; never delete, replace or activate it for them.
   A BLOCKING item about `.git/config`, a symlink, extra files in `.githooks` while `core.hooksPath = .githooks` is active (an older install), a global `core.hooksPath`, or a `.git` file means the vault may not be trusted or the hook would not run: report the listed keys as they are, do not edit that file yourself, and let the user decide.
   Also read the full hook text the plan prints and tell the user it will run on every commit.
5. **Ask, then apply.** Only after a clear "yes" to "do you want to apply this?" run `python3 ~/.cogiforge/tools/adopt.py '/absolute/path/to/vault' --apply --confirm <sha>`, where `<sha>` is the `plan-sha256:` line that the dry run you showed the user ended with (never a sha from an older run). A "maybe" or silence is a no.
6. **The tool writes, you do not.** Do not edit the user's notes, `areas.txt`, hooks or baseline by hand. Never touch an existing note.
7. **No invented links, nothing about the person.** Do not propose links to lower the debt unless the user asks and you can point at the sentence that justifies each one. Do not infer who they are from their folder names.
8. **Talk to the user in the language they write in.** Fixed tokens (paths, `areas.txt`, rc codes) stay as they are.

## The steps

### 0. A stable copy in `~/.cogiforge` (you, before the dry run)

This plugin installs Cogiforge 0.1.1, commit `1f0d9cc38ead38801fc3b2153e1f90f952628eb6`. If the download fails (no internet, GitHub down, or the commit is not found), show the message as it is and stop; run nothing from a download that failed, and the person deletes any leftover `~/.cogiforge.new` themselves.

- `~/.cogiforge` does not exist: download it. The download goes to `~/.cogiforge.new` and only becomes `~/.cogiforge` whole, so an interrupted download never leaves a half folder under the real name.

```bash
{ [ -n "$HOME" ] && [ "$HOME" != "/" ] || { echo "STOP: HOME is not set"; false; }; } && { [ ! -e ~/.cogiforge ] && [ ! -e ~/.cogiforge.new ] || { echo "STOP: ~/.cogiforge or ~/.cogiforge.new already exists"; false; }; } && git init -q ~/.cogiforge.new && git -C ~/.cogiforge.new fetch -q --depth 1 https://github.com/Arthuro0103/cogiforge.git 1f0d9cc38ead38801fc3b2153e1f90f952628eb6 && git -C ~/.cogiforge.new -c advice.detachedHead=false checkout -q FETCH_HEAD && { [ "$(git -C ~/.cogiforge.new rev-parse HEAD)" = "1f0d9cc38ead38801fc3b2153e1f90f952628eb6" ] || { echo "STOP: the download is not the pinned commit"; false; }; } && rm -rf ~/.cogiforge.new/.git && printf '%s\n' 1f0d9cc38ead38801fc3b2153e1f90f952628eb6 > ~/.cogiforge.new/.cogiforge-commit && mv ~/.cogiforge.new ~/.cogiforge
```

- It exists: read its installed version ONLY from `~/.cogiforge/.cogiforge-commit` (the commit hash the download wrote). Do not read the plugin's own version from `~/.cogiforge/plugin/.claude-plugin/plugin.json`: the plugin's version is not the Cogiforge version. If the file is missing, the version is unknown: treat it as another version (ask before replacing it).
- If `~/.cogiforge/.git` exists, it is a clone of the repo (maybe the person's own development copy): this skill NEVER replaces it. If its commit is the pinned one (`git -C ~/.cogiforge rev-parse HEAD`), use it; if not, tell the person to update it themselves and stop.
- Same hash (`.cogiforge-commit` equals `1f0d9cc38ead38801fc3b2153e1f90f952628eb6`): same version, use it as it is.
- Another version, no `.git`: show the two hashes (the pinned one, `1f0d9cc38ead38801fc3b2153e1f90f952628eb6`, against the one read, or "unknown") and ask before replacing it. Never replace it without a yes. Only after a yes, with one chain:

```bash
{ [ -n "$HOME" ] && [ "$HOME" != "/" ] || { echo "STOP: HOME is not set"; false; }; } && { [ -f ~/.cogiforge/tools/adopt.py ] && [ ! -e ~/.cogiforge/.git ] || { echo "STOP: ~/.cogiforge is missing, incomplete, or a git clone"; false; }; } && { [ ! -e ~/.cogiforge.new ] && [ ! -e ~/.cogiforge.old ] || { echo "STOP: ~/.cogiforge.new or ~/.cogiforge.old is left from an earlier try"; false; }; } && git init -q ~/.cogiforge.new && git -C ~/.cogiforge.new fetch -q --depth 1 https://github.com/Arthuro0103/cogiforge.git 1f0d9cc38ead38801fc3b2153e1f90f952628eb6 && git -C ~/.cogiforge.new -c advice.detachedHead=false checkout -q FETCH_HEAD && { [ "$(git -C ~/.cogiforge.new rev-parse HEAD)" = "1f0d9cc38ead38801fc3b2153e1f90f952628eb6" ] || { echo "STOP: the download is not the pinned commit"; false; }; } && rm -rf ~/.cogiforge.new/.git && printf '%s\n' 1f0d9cc38ead38801fc3b2153e1f90f952628eb6 > ~/.cogiforge.new/.cogiforge-commit && mv ~/.cogiforge ~/.cogiforge.old && mv ~/.cogiforge.new ~/.cogiforge && rm -rf ~/.cogiforge.old
```

  The old copy is only renamed after the new one is complete, and only deleted after the new one took its place. If the chain stops before the first `mv`, nothing changed. If the second `mv` fails, run `mv ~/.cogiforge.old ~/.cogiforge` to go back. If only the last `rm` fails, the new copy is already in place and `~/.cogiforge.old` is left for the person to delete.
  Leftovers: if only `~/.cogiforge.old` exists (no `~/.cogiforge`), a swap stopped in the middle: run `mv ~/.cogiforge.old ~/.cogiforge` to go back, and only then try again. If `~/.cogiforge.new` exists and is not in use, it is a clone that did not finish: the person deletes it themselves and tries again. This skill never deletes `~/.cogiforge.old` or `~/.cogiforge.new` by itself outside the chain above. With two sessions at the same time, the second one stops at the `STOP` about leftovers.
  Vaults already adopted keep pointing at `~/.cogiforge`, so replacing it updates their hook too.

### 1. Dry run (you)

```bash
python3 ~/.cogiforge/tools/adopt.py '/absolute/path/to/vault'
```

That prints the plan and writes nothing. For the same data in JSON, to read yourself, add `--json`.

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
python3 ~/.cogiforge/tools/adopt.py '/absolute/path/to/vault' --apply --confirm <plan-sha256>
```

`<plan-sha256>` is the one from the dry run the user saw.

Read its output and report what was written. Exit codes: `0` ok · `1` something pending · `2` usage or no confirmation · `3` vault unreadable · `5` the plan changed since the preview (nothing was written: run the dry run again, show the user the new plan, ask again).
Suggest a test: add a note with no link and run `git commit`; the hook should block it. Commit nothing yourself unless asked.

## What adopt does NOT guarantee

1. That the Cogiforge copy is trustworthy: it checks that three scripts exist at `cogiforge.home`, not who wrote them.
2. That a hook you approved, or a vault you cleaned by hand after a block, is safe: it judges what it sees at that moment.
3. That the debt numbers are complete: skipped, unreadable and non-UTF-8 notes are listed, not measured.
4. That your global git config, your `PATH` or your shell are not hostile.

## Never

- Never run `git init` or `--apply` before the plan was read and confirmed, and never use `--no-verify`.
- Overwrite or edit an existing note or config file, or activate a hook you did not generate.
- Call a vault "fine" when notes were skipped, or when it was empty ("nothing to adopt" is not OK).
