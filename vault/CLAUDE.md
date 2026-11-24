# CLAUDE.md: how this workbench operates

A creative workbench: work, school and personal life in the same place. You (Claude) organize projects,
ideas and tasks, help write and plan, and improve together with whoever uses it. Obsidian opens `vault/`;
you run at the repo root and read and write **only inside `vault/`**.

## First time

First session: run the `cf-onboard` skill. Then create the first project with the `cf-new-project` skill (it registers it in `projects/_index.md` and runs `tools/hub.py`).

## Shared mode

If `roles.txt` exists in this folder, read `docs/TEAMS.md` before doing anything else; without it, ignore shared mode.

## Folders

`inbox/` raw capture · `notes/<area>/` processed notes (the folder is set by the note's `area:`;
the areas are whatever the user configures) · `projects/<name>/instructions.md` root of each project ·
`memory/` what the user said (`profile`, `patterns`, `decisions`, `ideas/_pains.md`) · `tasks/`
one note per task, in the **TaskNotes** plugin format (see *Tasks* below).

## The target comes first

**An item is only processed when a file that already existed changed.** The note is the trace,
not the product. Measured in the **author's own vault** (not yours; see `WHY.md`): a note born from a conversation
reached a project file in 4 of 4; one born from a loose file, in 0 of 43. So:

1. Name the target **before** writing: `project::` · `article::` · `question::` · `task::` · `none`.
   `none` is a legitimate answer; the item stays in the inbox with a date, it is not deleted.
2. Write the note and the diff in the target in the same commit. The note's frontmatter carries `target:` (the path that changed, or `none`); a new note under `notes/` without it only gets a warning from the commit hook (`target: block` in `gate.txt` makes it block).
3. A direct conversation is worth more than the inbox. The inbox is a fallback.

## Writing rules

- A title is a statement of up to 10 words, never a category.
- Link by full path from `vault/`: `[[projects/example-my-first-project/instructions|example]]`. It only exists when the connection is real.
- **No `## Connections` block at the bottom.** The link goes in the body, in the middle of the argument.
- A new file that talks about a project carries a wikilink to its root.
- Nothing claims something about the user that they did not say. You **propose** in `memory/observations.md`; it only enters `memory/` with the user's "yes", with a date and a verbatim quote.

## Tasks

Tasks belong to the **TaskNotes** plugin (public, MIT). Each one is a note in `tasks/` with the `task` tag
and this header: `status: open | in-progress | done`, `priority: none | low | normal | high`,
`projects:` with a full-path link to the project root. The plugin creates and lists tasks in the
Obsidian interface; you (Claude) can also write the file directly, in the same format. `tasks/`
is exempt from the orphan gate and the gate does not judge the YAML there (the plugin adds its own fields), but
a dead link inside a task still fails.

The orphan gate blocks by default. `vault/gate.txt` (`orphan: block` or `orphan: warn`) is the user's setting: never change it yourself, and the leak scanner ignores it either way.

## Connection map (optional)

If the user installed **graphify** (public, Apache-2.0) and ran `/graphify vault` at the repo root,
`graphify-out/GRAPH_REPORT.md` exists: read it before looking for connections between notes. The graph is generated:
do not edit it and do not commit it.

## Skills

Each skill describes itself in `.claude/skills/*/SKILL.md`; the same table for agents that do not load them is in `AGENTS.md`.

How context loads and how to keep it small: `docs/CONTEXT.md`.

Sync conflicts and duplicate files (`x (1).md`, conflicted copy): `docs/SYNC.md`.

## Never

Write outside `vault/`. Delete a note without being asked. Fill `memory/` without the user's words.
