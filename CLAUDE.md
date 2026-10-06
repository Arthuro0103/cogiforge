# CLAUDE.md: cogiforge

You are at the **repo root**. The workbench (the user's notes, projects and memory) lives in `vault/`.
**Before acting, read `vault/CLAUDE.md`**: it says how the workbench operates. This file only carries the
rules and the commands. Each rule has the mistake that originated it in [POR-QUE.md](POR-QUE.md).

## The rules

1. **Read and write only inside `vault/`.** `core/`, `tools/`, `tests/` and `.githooks/` change only if the user asks.
2. **Do not write about the user what they did not say.** You propose in `vault/memory/observations.md`; a line only enters `vault/memory/profile.md` with the user's "yes", with a date and the verbatim phrase.
3. **The target comes first.** An item is only processed when a file that already existed changed. Name the target before writing: `project::`, `article::`, `question::`, `task::` or `none`.
4. **Link by full path from `vault/`**, in the middle of the text, only where the connection is real. No `## Connections` block at the bottom.
5. **A note title is a statement of up to 10 words**, not a category.
6. **Do not bypass the hook.** If the commit was blocked, the message names the file and the reason: fix the file. `--no-verify` only if the user says so.
7. **Never run `git push`, nor create a remote, nor make anything public without the user's order.**
8. **Personal data does not enter the repo** (machine path, email, phone, CPF, names from the private list). The hook blocks it; if it blocks, remove the data.
9. **A task is a TaskNotes plugin note** in `vault/tasks/` (`status`: `open`, `in-progress`, `done`; full-path link to the project in `projects:`). Details in `vault/CLAUDE.md`.
10. **If `graphify-out/GRAPH_REPORT.md` exists, read it before looking for connections between notes.** It is generated: do not edit it, do not commit it.
11. **A check that touched nothing is not OK.** If you could not verify, say `NOT_VERIFIED` and why, instead of saying it is clean.

## Commands

| What for | Command |
|---|---|
| enable the hook and prove it works | `sh install.sh` |
| check links, areas and frontmatter | `python3 core/gate.py` |
| list orphan notes | `python3 core/ring.py` |
| look for personal data | `python3 core/leak.py .` |
| rewrite each project's file-list block | `python3 tools/hub.py` |
| connection map (optional, needs graphify installed) | `/graphify vault` at the repo root |
| run the tests (needs `pytest`; after `sh install.sh`) | `python3 -m pytest -q` |
| break each check and require a red test | `python3 tests/mutate.py` |

The gate only checks what is **inside** `vault/`: a file outside fails with an error, never as OK.

## Skills (in `.claude/skills/`)

`onboard` (onboarding) · `open-session <project>` · `close-session` · `task-observer` (only proposes) ·
`claude-corner` (when the user leaves; only proposes) · `adapt-skill` (the user makes their own skill from
a worksheet; you do not write the skill alone). The worksheets live in `vault/skill-worksheets/`.

## Language

Skills and docs are in English; Claude replies in the language the user writes in.
