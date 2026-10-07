---
name: close-session
description: Closes the workday on the workbench. Writes the day's diary (vault/memory/diary/), one briefing per session (vault/memory/briefings/) with a full-path link to the project root in the body, collects pains from the user's own words into vault/memory/ideas/_pains.md, opens a task in vault/tasks/ for whatever is left pending, and runs the verifiers if they exist. A new skill or new project comes out only as a proposal. Commits only if the user says so and never pushes. TRIGGERS - "fecha a sessão", "vou parar por hoje", "/close-session", "what did we do today", "summarize the day". Do NOT trigger to summarize a short conversation with no work, to open a session (that is open-session), nor to observe process (that is task-observer).
---

# close-session: what is left of the day, written down before it is forgotten

## Why it exists

Work ends and the context vanishes: in the next session nobody knows what was left pending, what
annoyance came up, what decision was made. Closing from memory records what you remember, not what
happened. Closing with a method turns the session into four things: diary, briefing, pains, tasks.

## The rules

1. **The source is what happened, not what I remember.** Every number or fact in the briefing comes from a
   command run in this session (`git log`, `git diff --stat`, `ls`). With no command, I write "not measured".
2. **A pain only with the user's words.** `_pains.md` gets the phrase the user **wrote**, in quotation marks.
   My phrase, or the label of a menu option they clicked, is not their words: it does not go in.
3. **Link only if the file exists.** Check with `test -f` before writing the wikilink. Full path
   from `vault/`, in the middle of the argument. **Never** a `## Connections` block at the bottom.
4. **A section with no content is omitted.** A weak session produces a short briefing. "No pain today" is a valid answer.
5. **I propose, I do not assert.** A new skill, a new project, a change to `profile.md`, `patterns.md` or
   `decisions.md`: they come out as a proposal in the briefing. The user is the one who writes there.
6. **No order, no commit; never push.** Ask before committing. This skill pushes nothing.

> Talk to the user and write prose (notes, briefings, profile lines) in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, status values, paths, enums) stay exactly as written.

## The steps

### 1. Gather what happened (you, Claude)

```bash
git log --since=midnight --oneline --stat 2>/dev/null | head -40 || true
git status --short
ls -t vault/tasks/ | head -10
```

If `git log` shows nothing (repo with no commits), say "not measured: no commits" and go by the conversation.
Cross it with what was said in it. Find the project(s) touched: each one must have
`vault/projects/<name>/instructions.md`. If it does not, say so and ask which it is.

### 2. Write the briefing, one per session (you)

File `vault/memory/briefings/YYYY-MM-DD-<slug>.md`, a short slug of the subject:

```yaml
---
type: session-briefing
date: YYYY-MM-DD
projects: [<name>]
---
```

Title: a statement of up to 10 words about what the session produced. Sections, in this order, **omitting
the empty ones**: *What happened* (2-3 paragraphs) · *What was measured* (command and number) · *What the user
corrected* (the quoted words) · *What is still standing* (pending item with next step) · *What could be born*
(proposal, with "why now"). The link to the root goes in the body, for example:
`... moved forward on [[projects/<name>/instructions|<name>]] up to point X`.

### 3. Write or append the diary (you)

`vault/memory/diary/YYYY-MM-DD.md`. In shared mode (`vault/roles.txt` exists) it is
`vault/people/<handle>/diary/YYYY-MM-DD.md`, with `<handle>` found by matching `git config user.email` in `roles.txt`;
never write in another person's folder. If it already exists, **append** a section; never rewrite what is
there. Three to five lines per project: what moved, what got stuck, a full-path link to the briefing
(`memory/briefings/...`).

### 4. Collect pains (you)

Reread what the user **typed** in the session: complaint, workaround, something done by hand, "this again".
Append to the end of `vault/memory/ideas/_pains.md`, one per line, in this format:

```
YYYY-MM-DD | "verbatim quote from the user" | <briefing or project it came from>
```

If the file does not exist, do not create it: say it belongs to the workbench structure and leave the pains in the
briefing, in the section *What is still standing*. If the quote is not verbatim, do not write it.

### 5. Open a task for whatever is left pending (you)

A pending item with a concrete next step becomes a task in the **TaskNotes** plugin format, in
`vault/tasks/<slug>.md` (the slug comes from the title; if the file already exists, add `-2`). No ID in the name:
the plugin recognizes a task by the `task` tag, not by the file name. `status` is `open`, `in-progress` or
`done`; `priority` is `none`, `low`, `normal` or `high`. Ask for the priority if it is not obvious.

```yaml
---
tags:
  - task
title: <verb in the infinitive + what>
status: open
priority: normal
projects:
  - "[[projects/<name>/instructions|<name>]]"
---
```

The link in `projects` is a **full path** (the gate checks it). Body: one line on what to do and one
on "done when".

### 6. Run the verifiers, if they exist (one command each)

```bash
test -f core/gate.py && python3 core/gate.py || echo "gate.py does not exist yet: skipped"
test -f core/ring.py && python3 core/ring.py --gate || echo "ring.py does not exist yet: skipped"
```

If one fails, show the output and fix **only what is yours** (the briefing you just wrote). Do not
hide a failure: report it.

### 7. Deliver and ask (you)

Chat, at most 8 lines: paths of the files created, how many pains collected, tasks opened,
result of the verifiers (or "skipped: they do not exist"). Ask: *"do you want me to commit?"* Only with a yes,
commit the files of this skill, and **no `git push`**.

## Never

- Run `git push`, or commit without the user's order.
- Put my words in `_pains.md`.
- Write to `profile.md`, `patterns.md`, `decisions.md` or `vault/notes/`.
- Create a skill or project: only propose.
- Delete or rewrite a diary that already exists.
