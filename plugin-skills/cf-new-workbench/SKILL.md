---
name: cf-new-workbench
description: Creates a new Cogiforge workbench in a folder the person picks, from the plugin's own files. TRIGGERS - "create a cogiforge workbench", "set up a second brain with cogiforge", "new workbench". Do NOT trigger to put the gate on a vault that already exists (cf-adopt), nor inside a workbench that is already set up (cf-onboard).
---

# cf-new-workbench: make a new workbench

The plugin carries the whole Cogiforge repo. This skill copies it into a fresh folder, turns the commit gate on and makes the first commit. The 17 working skills come along inside the copy, in `.claude/skills/`.

## Rules

1. **One question at a time.** The only question is the folder. Ask for an absolute path and suggest `~/cogiforge-workbench`. Expand `~` yourself before you use it.
2. **Never overwrite.** If the folder exists and is not empty, stop and say so. Ask for another folder. Do not delete anything to make room.
3. **Windows is not covered here.** If the system is Windows, say: use "Use this template" on GitHub and run `install.ps1`. Stop.
4. **Do not skip the gate.** Never use `--no-verify`. If the first commit is blocked, show the hook's message and stop.
5. Talk to the person in the language they write in, in simple words.

## Steps

Let `DEST` be the folder and `ROOT` be `${CLAUDE_PLUGIN_ROOT}`.

1. Ask for `DEST`. Check it: it must not exist, or must be an empty folder.
2. Copy and clean. The copy leaves out `.claude-plugin/` and `plugin-skills/` (they belong to the plugin, not to the workbench), and any `.git`:

```bash
mkdir -p "$DEST" && cp -R "${CLAUDE_PLUGIN_ROOT}/." "$DEST/"
rm -rf "$DEST/.claude-plugin" "$DEST/plugin-skills" "$DEST/.git"
```

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
