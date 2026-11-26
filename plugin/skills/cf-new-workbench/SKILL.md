---
name: cf-new-workbench
description: Creates a new Cogiforge workbench in a folder the person picks, by downloading Cogiforge 0.1.2 from GitHub, pinned to one commit and checked by hash. TRIGGERS - "create a cogiforge workbench", "set up a second brain with cogiforge", "new workbench". Do NOT trigger to put the gate on a vault that already exists (cf-adopt), nor inside a workbench that is already set up (cf-onboard).
---

# cf-new-workbench: make a new workbench

The plugin carries only instructions (Markdown); the code comes from GitHub. This plugin installs Cogiforge 0.1.2, pinned to commit `74177d483c444ee628114f56770fe5d111e97b29` (tag `v0.1.2`), and the command checks that hash before it runs anything from the download. This skill downloads that commit into a fresh folder, turns the commit gate on and makes the first commit. The 17 working skills come along inside the copy, in `.claude/skills/`.

## Rules

1. **One question at a time.** The only question is the folder. Ask for a path and suggest `~/cogiforge-workbench`. You write it as an ABSOLUTE path in `DEST='...'`: expand `~` yourself to the real home folder, with no slash at the end. If the path contains a single quote, ask for another folder.
2. **Never overwrite.** If the folder exists and is not empty, stop and say so. Ask for another folder. Do not delete anything to make room. The checks run BEFORE the download, in the same command (step 2): if one fails, nothing is downloaded and nothing is deleted.
3. **Windows is not covered here.** If the system is Windows, say: use "Use this template" on GitHub and run `install.ps1`. Stop.
4. **Do not skip the gate.** Never use `--no-verify`. If the first commit is blocked, show the hook's message and stop.
5. Talk to the person in the language they write in, in simple words.

## Steps

1. Ask for the folder.
2. Run this ONE command, changing only the path between the single quotes. It needs `git` and an internet connection. It is one command on purpose: every Bash call in Claude Code starts a new shell, so nothing here may depend on a variable from an earlier call. Never split it into lines or into separate calls. Each guard prints `STOP: <reason>` and ends the chain; repeat the reason in plain words and ask for another folder (for the git case, the question is the global git identity: tell the person to run `git config --global user.name "..."` and `git config --global user.email "..."`, then try again).

```bash
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR && DEST='/absolute/path/to/the/folder' && { case "$DEST" in /*) true ;; *) echo "STOP: not an absolute path"; false ;; esac; } && { case "$DEST/" in */./*|*/../*) echo "STOP: the path has . or .. in it"; false ;; *) true ;; esac; } && { [ "${DEST%/}" != "" ] && [ "${DEST%/}" != "${HOME%/}" ] || { echo "STOP: / and the home folder are never used"; false; }; } && { [ ! -e "$DEST" ] || { [ -d "$DEST" ] && [ -r "$DEST" ] && [ -x "$DEST" ] && [ -z "$(ls -A "$DEST")" ]; } || { echo "STOP: the folder exists and is not empty"; false; }; } && { git -C / config user.name >/dev/null && git -C / config user.email >/dev/null || { echo "STOP: git has no global user.name or user.email"; false; }; } && git init -q "$DEST" && git -C "$DEST" fetch -q --depth 1 https://github.com/Arthuro0103/cogiforge.git 74177d483c444ee628114f56770fe5d111e97b29 && git -C "$DEST" -c advice.detachedHead=false checkout -q FETCH_HEAD && { [ "$(git -C "$DEST" rev-parse HEAD)" = "74177d483c444ee628114f56770fe5d111e97b29" ] || { echo "STOP: the download is not the pinned commit"; false; }; } && rm -rf "$DEST/.git" && cd "$DEST" && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge 0.1.2"
```

If the command stops without a `STOP:` line, say that it stopped and show what it printed; never guess which step failed. The chain removes only `.git` (the workbench starts its own history). It keeps `plugin/` and `.claude-plugin/`: the workbench is a copy of the repo, and its `tests/test_plugin.py` reads those folders.

3. If the download fails (no internet, GitHub down, or the pinned commit is not found), show the message as it is and stop; nothing was deleted. The folder then holds only an unfinished download: run nothing from it. The same goes for `STOP: the download is not the pinned commit`: never run `install.sh` or anything else from that folder. The person deletes the folder themselves and tries again; this skill never deletes it.
4. If something AFTER the checked download fails (`install.sh`, or the hook blocked the commit), show the message as it is and stop. The folder already has the files and this skill NEVER deletes it. After the cause is fixed, to try again, run this in the folder (same absolute path as `DEST`). This retry command is only for the folder the main command just downloaded, never for a folder that stopped with `STOP: the folder exists and is not empty`. If git says `nothing to commit`, the first commit already happened (check with `git -C '<folder>' log --oneline -1`) and all is well:

```bash
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR && DEST='/absolute/path/to/the/folder' && { case "$DEST" in /*) true ;; *) echo "STOP: not an absolute path"; false ;; esac; } && { [ -f "$DEST/install.sh" ] && [ -f "$DEST/core/memory.py" ] || { echo "STOP: this folder is not a Cogiforge workbench"; false; }; } && cd "$DEST" && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge 0.1.2"
```

   Or the person deletes the folder themselves and the skill runs again.
5. Tell the person, in plain words:
   - The workbench is in `DEST`, the gate is on, and the first commit passed it.
   - The 18 skills are already inside the workbench, in `.claude/skills/`. They show up when Claude Code is opened IN that folder, not here.
   - Next: close this session, run `cd DEST`, run `claude`, and type `/cf-onboard`.
   - To open the notes in Obsidian, open the `vault/` folder inside it.
