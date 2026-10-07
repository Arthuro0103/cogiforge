# Syncing the vault without losing notes

The most repeated pain in the research behind this project: two copies of a note collide, and a sync tool
leaves duplicates behind (one source: "i had .md duplicated up to 56 times", iCloud). This page says what
to do about it, and what the detector in this repo does and does not catch.

## Recommended: git is the sync

The vault is a git repository. Use it as one.

- **Before you start working:** `git pull` (when you have a remote), so you begin from the latest copy.
- **When you close the session:** `git add -A && git commit`, and `git push` if you have a remote.
- Two machines or two people: never edit the same note on both without a pull in between. Git then shows a
  real conflict you can resolve, instead of a silent second copy.

The pre-commit hook has a fourth guard for this: it blocks a commit that carries a sync-tool conflict file
(see "What the detector catches" below). `git commit --no-verify` is the deliberate bypass.

## A cloud folder with git inside it: the real risks

iCloud Drive, OneDrive and Dropbox sync files, not repositories. Putting a `.git` folder inside one means two
sync systems fight over thousands of small files that git expects to change atomically.

| Risk | What was reported | Status |
|---|---|---|
| Duplicate notes (`name 2.md`, `name (1).md`, `conflicted copy`) | The research cited this more than any other pain, with iCloud the most named | [VERIFY] 2026-10-07: reproduced from user reports only, not from an official statement |
| Corrupted git index or objects, odd `.git` files with ` 2` suffixes | Reports of the cloud client rewriting or duplicating files inside `.git` while git runs | [VERIFY] 2026-10-07: not checked against an open source or vendor doc |
| Files not downloaded ("dataless", `.icloud` placeholders) | Tools that read the folder see a stub instead of the note | [VERIFY] 2026-10-07: behavior depends on the OS version and the "Optimize storage" setting |
| Windows | iCloud for Windows is not a good home for a vault or a repo (see below) | [VERIFY] 2026-10-07 |

None of these is certain for your setup. They are real enough that the safe default is the next section.

## If you keep the vault in a cloud folder anyway

1. **Keep `.git` out of the sync.** Two ways people use, both [VERIFY] 2026-10-07 against the vendor docs
   before you trust them:
   - iCloud on macOS: a folder whose name ends in `.nosync` is skipped by iCloud. Rename `.git` to
     `.git.nosync` and make `.git` a symlink to it. [VERIFY] 2026-10-07: confirm in Apple's documentation,
     and that git accepts a symlinked `.git`.
   - Put the repository outside the synced folder and keep only the notes inside it, or use a
     `--separate-git-dir` clone ([VERIFY] 2026-10-07: check `git init --separate-git-dir` in the git docs).
2. **Do not run two sync systems on one folder.** git plus iCloud is already two. Add Obsidian Sync or
   Dropbox on top and you have three writers.
3. **Close the app on one machine before you open it on the other**, and wait for the cloud client to say it
   finished. Most duplicates start from an edit made before the first machine had uploaded.
4. **Do not use iCloud for Windows for a vault.** [VERIFY] 2026-10-07: the reports favor OneDrive, Syncthing
   or plain git there; check the current state of the client before you decide.

## The conflict already happened

1. Run the detector to list every leftover: `python3 core/conflicts.py vault`.
2. For each pair, compare them: `diff "note.md" "note (1).md"` (or open both side by side).
3. Keep the one you want. If both hold edits, copy the missing text into the keeper by hand.
4. Delete the other. Placeholders (`.name.md.icloud`) are not copies: open the folder in Finder or the Files
   app and let the cloud client download the real file, then re-run the detector.
5. Commit. If the hook still blocks, the output names the file and the reason.

## What the detector catches, and what it does not

`core/conflicts.py` (`--staged` for the hook, `--json` for scripts, `--selftest` to prove it works) flags:

- `name (conflicted copy ...)` (Dropbox style)
- `name (Case Conflict)` (Dropbox)
- `name.sync-conflict-<date>-<id>.md` (Syncthing)
- `.name.md.icloud` (iCloud, not downloaded)
- `name (1).md` and `name 2.md`, **only when `name.md` exists in the same folder**. A real note called
  `Chapter 2.md` with no `Chapter.md` is not a conflict, and is not flagged.

It does **not** catch:

- A duplicate whose original was already deleted (the sibling rule lets it through, on purpose).
- Two copies that kept the same name because one silently overwrote the other. That loss leaves no trace
  for any detector; git history is the only recovery.
- Conflict naming from tools it does not know (OneDrive's `name-<MACHINE>.md`, Obsidian Sync's merge
  markers, Google Drive). [VERIFY] 2026-10-07: the exact naming of each is not checked against its docs.
- Corruption inside `.git`.

The output is `file:reason`, never the content. Exit codes: 0 clean, 1 found, 2 usage, 3 could not read
(never reported as clean).
