# CLAUDE.md: cogiforge

You are at the **repo root**. The workbench (the user's notes, projects and memory) lives in `vault/`.
**Before acting, read `vault/CLAUDE.md`** (how the workbench operates). This file carries the
rules and the commands. Each rule has the mistake that originated it in [WHY.md](WHY.md).

The same rules, for any agent, are in [AGENTS.md](AGENTS.md).

## The rules

1. **Read and write only inside `vault/`.** `core/`, `tools/`, `tests/` and `.githooks/` change only if the user asks.
2. **Do not write about the user what they did not say.** You propose in `vault/memory/observations.md`; a line only enters `vault/memory/profile.md` with the user's "yes", with a date and the verbatim phrase. The hook checks it (`core/memory.py`: format, date, the literal phrase in the source when the source is a file, invisible text).
3. **The target comes first.** An item is only processed when a file that already existed changed. Name the target before writing: `project::`, `article::`, `question::`, `task::` or `none` (the item stays in `vault/inbox/` with a date).
4. **Link by full path from `vault/`**, in the middle of the text (`[[projects/example-my-first-project/instructions|the project]]`), only where the connection is real. No `## Connections` block at the bottom.
5. **A note title is a statement of up to 10 words**, not a category.
6. **Do not bypass the hook.** If the commit was blocked, the message names the file and the reason: fix the file. `--no-verify` only if the user says so.
7. **Never run `git push`, nor create a remote, nor make anything public without the user's order.**
8. **Personal data does not enter the repo** (machine path, email, phone, CPF, names from the private list). The hook blocks it; if it blocks, remove the data.
9. **A task is a TaskNotes plugin note** in `vault/tasks/` (`status`: `open`, `in-progress`, `done`; full-path link to the project in `projects:`). Details in `vault/CLAUDE.md`.
10. **If `graphify-out/GRAPH_REPORT.md` exists, read it before looking for connections between notes.** It is generated: do not edit it, do not commit it.
11. **A check that touched nothing is not OK.** If you could not verify, say `NOT_VERIFIED` and why, instead of saying it is clean.

## Memory (loads in every session)

@vault/memory/profile.md
@vault/memory/patterns.md
@vault/memory/decisions.md

This is the user's own memory; rule 2 applies to it. Shared mode: each person adds the `@` lines for their
`vault/people/<handle>/memory/` files to their own `CLAUDE.local.md` (not versioned).

## Commands

| What for | Command |
|---|---|
| enable the hook, prove it works | `sh install.sh` |
| check links, areas and frontmatter | `python3 core/gate.py` |
| check the memory: format, date, the phrase in its source | `python3 core/memory.py [--staged]` |
| rewrite each project's file-list block | `python3 tools/hub.py` |
| find passages in the vault / check citations exist | `python3 tools/ask.py search "<question>"` · `python3 tools/ask.py cite <answer.md>` |
| run the tests (needs `pytest`) | `python3 -m pytest -q` |

The full table is in [AGENTS.md](AGENTS.md) (section Commands). The gate only checks **inside** `vault/`: a file outside fails, never as OK.

## Skills (in `.claude/skills/`)

`cf-onboard` · `cf-open-session <project>` · `cf-ask <question>` (answers only from the notes) · `cf-close-session` · `cf-task-observer` (only proposes) ·
`cf-claude-corner` (when the user leaves; only proposes) · `cf-adapt-skill` (the user makes their own skill; you do not write it alone) · `cf-new-project` (`tools/new_project.py`) · `cf-brand <mode>` (only in the user's words; `docs/BRAND.md`). Worksheets: `vault/skill-worksheets/`.

## Language

Skills and docs are in English; Claude replies in the language the user writes in.
