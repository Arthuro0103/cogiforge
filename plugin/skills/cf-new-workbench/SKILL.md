---
name: cf-new-workbench
description: Creates a new Cogiforge workbench in a folder the person picks, by downloading Cogiforge from GitHub at the plugin's version. TRIGGERS - "create a cogiforge workbench", "set up a second brain with cogiforge", "new workbench". Do NOT trigger to put the gate on a vault that already exists (cf-adopt), nor inside a workbench that is already set up (cf-onboard).
---

# cf-new-workbench: make a new workbench

The plugin carries only instructions (Markdown); the code comes from GitHub. This skill downloads Cogiforge at tag `v0.1.0` (the plugin's version) into a fresh folder, turns the commit gate on and makes the first commit. The 17 working skills come along inside the copy, in `.claude/skills/`.

## Rules

1. **One question at a time.** The only question is the folder. Ask for a path and suggest `~/cogiforge-workbench`. You write it as an ABSOLUTE path in `DEST='...'`: expand `~` yourself to the real home folder, with no slash at the end. If the path contains a single quote, ask for another folder.
2. **Never overwrite.** If the folder exists and is not empty, stop and say so. Ask for another folder. Do not delete anything to make room. The checks run BEFORE the download, in the same command (step 2): if one fails, nothing is downloaded and nothing is deleted.
3. **Windows is not covered here.** If the system is Windows, say: use "Use this template" on GitHub and run `install.ps1`. Stop.
4. **Do not skip the gate.** Never use `--no-verify`. If the first commit is blocked, show the hook's message and stop.
5. Talk to the person in the language they write in, in simple words.

## Steps

1. Ask for the folder.
2. Run this ONE command, changing only the path between the single quotes. It needs `git` and an internet connection. It is one command on purpose: every Bash call in Claude Code starts a new shell, so nothing here may depend on a variable from an earlier call. Never split it into lines or into separate calls. Each guard prints `STOP: <reason>` and ends the chain; repeat the reason in plain words and ask for another folder (for the git case, tell the person to run `git config --global user.name` and `git config --global user.email`, then try again).

```bash
DEST='/absolute/path/to/the/folder' && { case "$DEST" in /*) true ;; *) echo "STOP: not an absolute path"; false ;; esac; } && { [ "${DEST%/}" != "" ] && [ "${DEST%/}" != "${HOME%/}" ] || { echo "STOP: / and the home folder are never used"; false; }; } && { [ ! -e "$DEST" ] || { [ -d "$DEST" ] && [ -r "$DEST" ] && [ -z "$(ls -A "$DEST")" ]; } || { echo "STOP: the folder exists and is not empty"; false; }; } && { git config user.name >/dev/null && git config user.email >/dev/null || { echo "STOP: git has no user.name or user.email"; false; }; } && git clone -q -c advice.detachedHead=false --depth 1 --branch v0.1.0 https://github.com/Arthuro0103/cogiforge.git "$DEST" && rm -rf "$DEST/.git" && cd "$DEST" && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge 0.1.0"
```

If the command prints nothing and stops, one guard failed: say which one. The chain removes only `.git` (the workbench starts its own history). It keeps `plugin/` and `.claude-plugin/`: the workbench is a copy of the repo, and its `tests/test_plugin.py` reads those folders.

3. If `git clone` fails (no internet, GitHub down), show its message as it is and stop; nothing was deleted.
4. If something AFTER the clone fails (`install.sh`, or the hook blocked the commit), show the message as it is and stop. The folder already has the files and this skill NEVER deletes it. After the cause is fixed, to try again, run this in the folder (same absolute path as `DEST`):

```bash
cd '/absolute/path/to/the/folder' && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge 0.1.0"
```

   Or the person deletes the folder themselves and the skill runs again.
5. Tell the person, in plain words:
   - The workbench is in `DEST`, the gate is on, and the first commit passed it.
   - The 17 skills are already inside the workbench, in `.claude/skills/`. They show up when Claude Code is opened IN that folder, not here.
   - Next: close this session, run `cd DEST`, run `claude`, and type `/cf-onboard`.
   - To open the notes in Obsidian, open the `vault/` folder inside it.
