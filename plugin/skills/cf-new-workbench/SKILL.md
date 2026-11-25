---
name: cf-new-workbench
description: Creates a new Cogiforge workbench in a folder the person picks, by downloading Cogiforge from GitHub at the plugin's version. TRIGGERS - "create a cogiforge workbench", "set up a second brain with cogiforge", "new workbench". Do NOT trigger to put the gate on a vault that already exists (cf-adopt), nor inside a workbench that is already set up (cf-onboard).
---

# cf-new-workbench: make a new workbench

The plugin carries only instructions (Markdown); the code comes from GitHub. This skill downloads Cogiforge at tag `v0.1.0` (the plugin's version) into a fresh folder, turns the commit gate on and makes the first commit. The 17 working skills come along inside the copy, in `.claude/skills/`.

## Rules

1. **One question at a time.** The only question is the folder. Ask for an absolute path and suggest `~/cogiforge-workbench`. Expand `~` yourself before you use it.
2. **Never overwrite.** If the folder exists and is not empty, stop and say so. Ask for another folder. Do not delete anything to make room. The empty-folder check is made BEFORE the download, in the same command (step 2): if it fails, nothing is downloaded and nothing is deleted.
3. **Windows is not covered here.** If the system is Windows, say: use "Use this template" on GitHub and run `install.ps1`. Stop.
4. **Do not skip the gate.** Never use `--no-verify`. If the first commit is blocked, show the hook's message and stop.
5. Talk to the person in the language they write in, in simple words.

## Steps

Let `DEST` be the folder.

1. Ask for `DEST`. Check it: it must not exist, or must be an empty folder.
2. Download and clean, as ONE chained command. It needs `git` and an internet connection. Every `&&` is a guard: `DEST` is not empty, not `/`, not `$HOME`; `DEST` does not exist or is an empty folder; the `rm` runs only after a download that worked, and it removes `.git` (the workbench starts its own history), `plugin/` and `.claude-plugin/` (they belong to the plugin, not to the workbench). Never split it into separate lines:

```bash
[ -n "$DEST" ] && [ "$DEST" != "/" ] && [ "$DEST" != "$HOME" ] && { [ ! -e "$DEST" ] || { [ -d "$DEST" ] && [ -z "$(ls -A "$DEST")" ]; }; } && git clone -q --depth 1 --branch v0.1.0 https://github.com/Arthuro0103/cogiforge.git "$DEST" && rm -rf "$DEST/.git" "$DEST/plugin" "$DEST/.claude-plugin"
```

If the command prints nothing and stops, one guard failed: say which one in plain words and ask for another folder. If `git clone` itself fails (no internet, GitHub down), show its message as it is and stop; `git clone` also refuses a folder that is not empty on its own.

3. Turn the gate on and commit:

```bash
cd "$DEST" && git init -q && sh install.sh && git add -A && git commit -qm "workbench from cogiforge 0.1.0"
```

If `install.sh` fails or the hook blocks the commit, show its message as it is and stop.

4. Tell the person, in plain words:
   - The workbench is in `DEST`, the gate is on, and the first commit passed it.
   - The 17 skills are already inside the workbench, in `.claude/skills/`. They show up when Claude Code is opened IN that folder, not here.
   - Next: close this session, run `cd DEST`, run `claude`, and type `/cf-onboard`.
   - To open the notes in Obsidian, open the `vault/` folder inside it.
