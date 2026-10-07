# Context: how it works in practice

Claude only knows what is in its context window right now. It does not remember last week. "Using context
well" means deciding, on purpose, **what is loaded every time, what is loaded only when needed, and what
stays on disk until someone asks**. This guide explains how cogiforge does it and how to keep it healthy.

## What loads in every session

Three things are read before you type anything:

| what | where | why it is there |
|---|---|---|
| the rules | `CLAUDE.md` at the repo root (and `AGENTS.md`, for tools that read that name) | how Claude must behave in this repo |
| the workbench manual | `vault/CLAUDE.md`, pointed to by the root file | folders, writing rules, which skill to use |
| the memory index | `vault/memory/` files that Claude reads at the start | what you told it about yourself |

**Why this must stay small.** Everything loaded every time is paid for in every session, before any work
happens, and a long instruction file is followed worse than a short one: the model skips lines, and the
important one gets lost among the rest. The rule of thumb is that a line belongs here only if forgetting it
would break something in most sessions. Everything else goes somewhere that loads on demand.

## What loads only when asked

| what | how it loads |
|---|---|
| one project | `/open-session <name>` reads that project's root, the last diary entries and its open tasks. **One project**, not all of them. |
| a skill | a skill's text enters the context only when it triggers. Its `description` is always visible so Claude can tell when to use it. |
| a worksheet | read when you or a skill points to it. See [vault/worksheets/](../vault/worksheets/). |
| an answer from your notes | `/ask` searches and returns only the matching passages, with citations. |

This is the reason `open-session` takes a name: loading every project in every session would make the
context large and mostly irrelevant.

## Where each thing lives

| folder | what goes in it | who writes it |
|---|---|---|
| `vault/memory/` | **what you said**: profile, patterns, decisions, pains. Dated, with your verbatim quote. | you, or Claude with your "yes" |
| `vault/notes/` | processed knowledge: one idea per note, title is a statement | you and Claude, after the target is named |
| `vault/projects/<name>/` | the root of each project, plus the files it produces | you and Claude |
| `vault/inbox/` | raw capture. Exempt from the orphan gate so capture is never blocked. | you |
| `vault/tasks/` | one note per task, in the TaskNotes plugin format | the plugin, you, Claude |

The split is about **authorship**: `memory/` is your voice, `notes/` is processed knowledge, `projects/` is
the work, `inbox/` is the unsorted pile. When a fact has no home, it probably is not ready to be a note yet.

## The golden rule

**Good context is specific, and it comes from what the person said. It never comes from what the model
assumed.**

- "I get stuck when I have to start a report" is context. "The user is a procrastinator" is a guess.
- A guess written into memory is read back in every later session as if it were a fact, and it gets worse
  each time it is reused. That is why cogiforge makes Claude **propose** and you **approve** ("yes") before
  anything about you is saved, with the date and your literal quote.
- If you cannot point to the sentence a line came from, delete the line.

## Signs of bad context, and what to do

| sign | what it usually means | what to do |
|---|---|---|
| Claude ignores an instruction | it is buried in a long file, or contradicts another line | shorten the file; keep one rule per line; move the rest to a project file |
| a file keeps growing and nobody reads it | it became a dump | split it by topic, or archive what is older than the project's current phase |
| Claude repeats an old rule that no longer applies | stale memory | fix or delete the line, and note the date of the change |
| Claude invents a detail about you | something was saved without your words | ask where the line came from; remove it if there is no quote |
| every session starts with long explanations from you | the project root is empty or vague | fill [project-brief](../vault/worksheets/project-brief.md) and [product-brief](../vault/worksheets/product-brief.md) once |
| answers sound generic | the context is generic | add one real quote, one real number, one real name of a role |

## When the project beats old material

Old exports, imported chats and early drafts are an **archive**, not a source of rules. They are useful for
recovering something that was never written down, never for reopening something decided later.
**When old material and the current project disagree, the project wins.** Concretely:

1. The latest entry in [decisions-log](../vault/worksheets/decisions-log.md) beats an older note.
2. When you count or compare things inside a project, leave out its raw `inputs/` first. Raw dumps are not
   rules, and counting them invents a conflict that does not exist.
3. If you find a real contradiction, do not pick silently: ask, then record the answer with its date.

## A practical budget

These are targets, not limits enforced by code. They exist so the always-loaded part stays small.

| item | target | if it is over |
|---|---|---|
| root `CLAUDE.md` | up to about 60 lines | move rules that apply to one project into that project's root |
| `vault/CLAUDE.md` | up to about 100 lines | move examples to a note and link them |
| each project root (`instructions.md`) | 1 to 2 screens, about 80 lines | move history to the diary; keep target, deadline, decisions, open questions |
| a memory file | about 100 lines | split by topic, or archive by date |
| a skill | under 500 lines, `description` under about 1000 characters | split the method from the examples |
| what you paste into a chat | only what the question needs | link the file instead of pasting it |

Check your own setup with `wc -l CLAUDE.md vault/CLAUDE.md vault/projects/*/instructions.md`.

## Tips by situation

### Personal

- Start with [onboard](../.claude/skills/onboard/SKILL.md) and answer short. A refusal is an answer.
- Keep one project root per thing you care about. A hobby is a project too.
- Do the [weekly review](../vault/worksheets/weekly-review.md) for ten minutes: it is the cheapest way to keep memory current.
- Do not store anything you would not want to read aloud. Health, family and relationships only if you bring them up and ask to record them.

### Company or team

- Put the **product** and its **pains** in the project, not in personal memory: see
  [PRODUCT-AND-PAINS.md](PRODUCT-AND-PAINS.md).
- Use handles or roles instead of real names in anything that may be shared. Run `python3 core/leak.py .`
  before sharing a copy.
- Log every decision that costs something in the [decisions-log](../vault/worksheets/decisions-log.md), with who can reverse it.
- If team mode is enabled, personal context stays in the person's own folder and only product context is shared.

### School

- One project per subject or per large assignment. The deadline goes in the project root.
- Paste the teacher's rubric or the assignment text into the project's `inputs/` and link it from the root;
  do not retype it into `CLAUDE.md`.
- Write your own words about what confuses you. Claude should explain to your level, not to the textbook's.
- Use [project-brief](../vault/worksheets/project-brief.md) to declare the target ("what exists when this is handed in").

## Related

- [PRODUCT-AND-PAINS.md](PRODUCT-AND-PAINS.md): how the workbench learns your product and your pains.
- [vault/worksheets/](../vault/worksheets/): the fill-in sheets.
- [WHY.md](../WHY.md): the dated failures behind the rules.
