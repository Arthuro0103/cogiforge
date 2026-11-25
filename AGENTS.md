# AGENTS.md: how to operate this repository

This file is for any coding agent (Codex, Cursor, Gemini CLI, GitHub Copilot, Claude Code and others).
Gemini CLI no longer serves free, Google AI Pro or Ultra individual users since 2026-06-18 (they moved to
Antigravity CLI); it remains for Standard and Enterprise and for paid API keys. It reads `GEMINI.md`, and
this file only if `context.fileName` lists it (see `docs/USING-OTHER-MODELS.md`).
It states the same rules as `CLAUDE.md` and `vault/CLAUDE.md` without relying on any one model's
features. If this file and those two ever disagree, the two `CLAUDE.md` files win and this one is a bug:
please fix it. A test (`tests/test_agents_md.py`) fails when the rules drift apart.

You are at the **repo root**. The workbench (the user's notes, projects and memory) lives in `vault/`.
Obsidian opens `vault/`; you run at the repo root.

## Installed as a plugin?

If Cogiforge came as a Claude Code plugin, the plugin holds only two skills: `/cf-new-workbench` (builds a workbench in a folder you choose) and `/cf-adopt` (puts the gate on an existing vault). The 17 working skills live inside each workbench, in `.claude/skills/` (also reachable as `.agents/skills`), because they work on that folder's files with relative paths; Claude Code loads them when it is opened in the workbench, so they never appear in unrelated projects. Do not look for them in the plugin folder. Details: the README section "Install as a Claude Code plugin".

## The rules

1. **Read and write only inside `vault/`.** `core/`, `tools/`, `tests/` and `.githooks/` change only if the user asks.
2. **Never write about the user what they did not say.** Propose a line in `vault/memory/observations.md`. A line enters `vault/memory/profile.md` only after the user says "yes", with a date and their verbatim phrase. The hook checks it (`core/memory.py`: format, date, the literal phrase in the source when the source is a file, invisible text).
3. **The target comes first.** An item (a chat export, a loose note, a video) counts as processed only when a file that already existed changed. Name the target before writing: `project::`, `article::`, `question::`, `task::` or `none`. `none` is a legitimate answer: the item stays in `vault/inbox/` with a date.
4. **Link by full path from `vault/`**, in the middle of the text, only where the connection is real, for example `[[projects/example-my-first-project/instructions|the project]]`. No `## Connections` block at the bottom of a note.
5. **A note title is a statement of up to 10 words**, not a category (prose-as-title).
6. **Do not bypass the hook.** If a commit is blocked, the message names the file and the reason: fix the file. Use `--no-verify` only if the user says so.
7. **Never run `git push`, create a remote, or make anything public without the user's order.**
8. **Personal data does not enter the repo** (machine path, e-mail, phone, tax id, names from the user's private list). The hook blocks it; if it blocks, remove the data.
9. **A task is a TaskNotes plugin note** in `vault/tasks/`: `status: open | in-progress | done`, `priority: none | low | normal | high`, and `projects:` with a full-path link to the project root. Details in `vault/CLAUDE.md`.
10. **If `graphify-out/GRAPH_REPORT.md` exists, read it before looking for connections.** It is generated: do not edit it, do not commit it.
11. **A check that touched nothing is not OK.** If you could not verify something, say `NOT_VERIFIED` and why, instead of saying it is clean.

## Memory: read it first

Agents that do not follow `@` imports (everything except Claude Code) must, at the start of every session and
before anything else, read `vault/memory/profile.md`, `vault/memory/patterns.md` and `vault/memory/decisions.md`
(in shared mode also your own `vault/people/<handle>/memory/` files). Rule 2 applies to them.

## Layout of `vault/`

`inbox/` raw capture (fallback, not the main door) · `notes/<area>/` processed notes; the folder is the
note's `area:` and the valid areas are listed in `vault/areas.txt` · `projects/<name>/instructions.md`
root of each project · `memory/` only what the user said · `tasks/` one note per task.

A minimal note:

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

## Commands

| What for | Command |
|---|---|
| enable the hook and prove it works | `sh install.sh` |
| check links, areas and frontmatter | `python3 core/gate.py` |
| list orphan notes | `python3 core/ring.py` |
| look for personal data (run before every commit that adds imported text) | `python3 core/leak.py .` |
| rewrite each project's file-list block | `python3 tools/hub.py` |
| find passages in the vault, check an answer's citations exist | `python3 tools/ask.py search "<question>"` · `python3 tools/ask.py cite <answer.md>` |
| which notes were used and which sit still, by area (`idle --project <name>` lists up to 3 for a project) | `python3 tools/usage.py` · `python3 tools/usage.py idle --project <name>` |
| record that an answer used notes (after the citations exist) | `python3 tools/ask.py cite <answer.md> --log "<question>"` |
| the memory: line format, date, the phrase in its source (when the source is a file), invisible text (`NOT_VERIFIED` is never OK) | `python3 core/memory.py` · `--staged` · `--json` |
| bytes a session loads, against its ceiling | `python3 core/budget.py` |
| does each citation (URL, arXiv id, DOI) exist and say what the text claims? (`NOT_VERIFIED` is never OK) | `python3 tools/citation.py <file.md>` · `--no-network` · `--selftest` · `--quotes NOTE.md` (a quote against the vault file linked on its line) |
| a verdict with a typed reason for "no value" (library for your own checks) | `python3 core/proof.py --selftest` |
| background subagents that stopped without finishing (STOPPED is the alarm) | `python3 tools/agents_watch.py [--session <id>] [--min 10]` |
| move the older dated lines of a memory file to an archive (plan first, `--apply` with the user's yes) | `python3 tools/cool.py memory/<file>.md --keep 40` |
| does a new session still find what the memory says? (`--static` reads the disk; `--run` asks a model; `NOT_VERIFIED` is never OK) | `python3 tools/recall.py` · `python3 tools/recall.py --run "<cmd>" --log` |
| memory lines gone stale (dead or moved path, aged file, `stale_after`, `superseded_by`; measures, never edits; `NOT_VERIFIED` is never OK) | `python3 tools/stale.py` · `--gate` · `--json` · `--threshold N` |
| which corrections repeat something the memory already said (reads `memory/observations.md`; lexical candidates, not a verdict) | `python3 tools/repeat.py` |
| a synthetic vault of N notes, and time and memory of every tool on it | `python3 tools/synth.py <dir> --notes 5000` · `python3 tools/bench.py --sizes 1000 5000 10000` |
| turn a chat export into notes in `vault/inbox/chats/` | `python3 tools/import_chats.py <conversations.json or export.zip>` |
| check that the command tables above cite only flags the scripts really have (reads the scripts without running them) | `python3 tools/flags.py --tables` · `python3 tools/flags.py <script.py>` |
| create a project (root, index row, checks) | `python3 tools/new_project.py <name> --target "<sentence>" [--dry-run]` |
| connection map (optional, graphify) | `/graphify vault` at the repo root |
| break each check and require a red test | `python3 tests/mutate.py` (`--shard I/N`, `--changed-since REF`) |
| run the tests (needs `pytest`) | `python3 -m pytest -q` |

Every script prints a non-zero exit code when it fails. Read the output, not only the exit code.

## The skills are plain text: any agent can follow them

The folder `.claude/skills/<name>/SKILL.md` is the Claude Code format: a Markdown file with a short
frontmatter (`name`, `description`) and steps in the body. Several agents find skills on their own, in
two folders: Claude Code, Cursor, GitHub Copilot and OpenCode read `.claude/skills`; Codex and Gemini CLI
read `.agents/skills`, which `sh install.sh` links to the same folder (who reads what, with the source
of each line: docs/USING-OTHER-MODELS.md). If your agent does not list them, each one is still just
text: **open the file and follow its steps as instructions**, the same way you would follow a README. Everything they ask for is done with files and
the commands above. Where a skill says "ask the user one question at a time", do exactly that.

| Skill (folder in `.claude/skills/`) | Use it when |
|---|---|
| `cf-onboard` | the first time, or when the user wants to update their profile: one question at a time, the output is the user's own words |
| `cf-open-session` | starting work on a project: read its root, the last diary entries and the open tasks |
| `cf-ask` | the user asks a question the notes may answer: answer only from the notes, with citations that `tools/ask.py cite` can check |
| `cf-close-session` | the day ends: diary, briefing, pains the user voiced, tasks for what is pending |
| `cf-task-observer` | during work: notice what repeats or was corrected, and only propose improvements |
| `cf-claude-corner` | the user is away: reread, connect and test outside `vault/`, and only propose |
| `cf-adapt-skill` | the user wants their own skill from a worksheet in `vault/skill-worksheets/`: you do not write it alone |
| `cf-extract-routine` | a routine lives only in someone's head: one question at a time until another person could follow it; the agent never declares it `validated` |
| `cf-brainstorm` | an idea is still loose: three different paths, a comparison by criteria the user picks, and a brief; nothing is built before their explicit yes |
| `cf-whats-real` | before a demo, delivery or launch: what works (with proof), what is simulated, what is unknown; checked again afterwards |
| `cf-import-knowledge` | the user brings an existing base (another vault, a folder, documents): run `tools/import.py`, read the report, then propose the triage from the inbox to `notes/`, target first; the user approves |
| `cf-adopt` | the user already has an Obsidian vault and does not want to start from zero or copy anything: dry-run `tools/adopt.py`, explain the plan and the debt measured today, apply only after a clear yes |
| `cf-know-my-product` | the user wants you to understand their product and pains: one question at a time, fills `projects/<name>/product.md` in their words, proposes the pain ranking |
| `cf-study` | the user wants to learn something their way: one question at a time on what, why, deadline, how and time; three level questions; a plan; then explain, recall, log. `mastered` only after a retest on another day, never without proof |
| `cf-new-project` | the user wants a new project: ask the name, then their own one-sentence target (copied unchanged), `--dry-run`, their "yes", then `tools/new_project.py` |
| `cf-brand` | the user wants their voice rules or a project's DNA, messaging, design system or manual: one question at a time, only their words, a "yes" before saving, no default colors; `manual` only assembles and marks what is empty. Checks with `tools/voice_check.py` and `tools/brand_preview.py` |
| `cf-new-rule` | the user hit a real, dated mistake and wants it to become a rule: the mistake first, then a pair of inputs, a test seen red, the rule, a mutation, a `WHY.md` entry; nothing outside `vault/` is written without their "yes" |

Shared mode: if `vault/roles.txt` exists, read `docs/TEAMS.md` first. After saving a note, run `python3 tools/hub.py`: a note in `projects/<name>/` enters the root's block on its own; a note in `notes/` only shows up there through the link in the body.

Features that depend on the agent (running a skill by `/name`, loading it by its description) are
conveniences. The rules in this file do not depend on them. More in
[docs/USING-OTHER-MODELS.md](docs/USING-OTHER-MODELS.md).

## Guides

[docs/EXPORTING-CHATS.md](docs/EXPORTING-CHATS.md) (bring your chat history in) ·
[docs/RESEARCH.md](docs/RESEARCH.md) (research with the vault) ·
[docs/USING-OTHER-MODELS.md](docs/USING-OTHER-MODELS.md) (other agents, what you lose)

## Language

Skills and docs are in English. Reply in the language the user writes in.
