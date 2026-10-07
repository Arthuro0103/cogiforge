# CLAUDE.md: how this workbench operates

A creative workbench: work, school and personal life in the same place. You (Claude) organize projects,
ideas and tasks, help write and plan, and improve together with whoever uses it. Obsidian opens `vault/`;
you run at the repo root and read and write **only inside `vault/`**.

## First time

1. Run the `onboard` skill: the user answers `_questions_about_me.md` (empty at the start), one question at a time. You invent nothing.
2. Create the project: copy `projects/example-my-first-project/` to `projects/<name>/`, edit the
   frontmatter (`type`, `status`, `declared_target`) and add the line to `projects/_index.md`.
3. Run `python3 tools/hub.py` so the project lists its files.

## Shared mode (teams, schools)

Shared mode is on only when `roles.txt` exists in this folder; without it, ignore this section.
`roles.txt` has one line per person: `handle  admin|member  email`.

- **Who am I talking to:** the e-mail from `git config user.email`, looked up in `roles.txt`. Not listed: say so and tell them to ask an admin for a line; write nothing.
- **Memory rule:** the rule below ("nothing claims something about the user that they did not say") applies to `people/<handle>/` of whoever is talking, which replaces `memory/` for them (`people/<handle>/memory/{profile,patterns,decisions}.md`, `inbox/`, `diary/`).
- **Never read another person's folder** (`people/<other>/`) to answer a question, not even to "help". `people/<handle>/private/` is gitignored: it is the only place for what is intimate.
- **Tasks** stay in the shared `tasks/`, with an `owner: <handle>` field in the header.
- **Roles:** a member does not edit `roles.txt` or `areas.txt`, nor create a `projects/<new>/instructions.md`; the pre-commit hook blocks it. That is a convention, not security: real enforcement is CODEOWNERS plus branch protection on the host.

## Folders

`inbox/` raw capture · `notes/<area>/` processed notes (the folder is set by the note's `area:`;
the areas are whatever the user configures) · `projects/<name>/instructions.md` root of each project ·
`memory/` what the user said (`profile`, `patterns`, `decisions`, `ideas/_pains.md`) · `tasks/`
one note per task, in the **TaskNotes** plugin format (see *Tasks* below).

## The target comes first

**An item is only processed when a file that already existed changed.** The note is the trace,
not the product. Measured: a note born from a conversation reached a project file in 4 of 4; one
born from a loose file, in 0 of 43. So:

1. Name the target **before** writing: `project::` · `article::` · `question::` · `task::` · `none`.
   `none` is a legitimate answer; the item stays in the inbox with a date, it is not deleted.
2. Write the note and the diff in the target in the same commit.
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

## Connection map (optional)

If the user installed **graphify** (public, Apache-2.0) and ran `/graphify vault` at the repo root,
`graphify-out/GRAPH_REPORT.md` exists: read it before looking for connections between notes. The graph is generated:
do not edit it and do not commit it.

## First note

Minimal template (the valid areas are in `areas.txt`; the folder is `notes/<area>/` and has the same name):

```
---
type: note
area: learning
project: example-my-first-project
date: 2026-10-03
---
# A title that is a statement of up to ten words

Body with the argument. The link goes here, in the middle:
[[projects/example-my-first-project/instructions|the project]] changes because of this.
```

After saving, run `python3 tools/hub.py`: a note in `projects/<name>/` enters the root's block
on its own; a note in `notes/` only shows up there through the link in the body.

## When to use each skill

| skill | when |
|---|---|
| `open-session` | when starting work on a project: say its name and it reads the root, the diary and the open tasks |
| `close-session` | when ending the day: diary, briefing, pains collected, tasks opened |
| `task-observer` | during the work: sees what repeats or was corrected and **only proposes** improvements |
| `claude-corner` | when the user says they are leaving: Claude rereads, connects and tests outside `vault/`, and **only proposes** |
| `onboard` | the first time and when the user wants to update the profile: one question at a time, the output is the user's own words |
| `adapt-skill` | when the user wants a skill of their own from a worksheet in `skill-worksheets/`; Claude does not write the skill alone |

## Never

Write outside `vault/`. Delete a note without being asked. Fill `memory/` without the user's words.
