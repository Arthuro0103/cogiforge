---
name: claude-corner
description: Claude's corner. When the user says they are leaving, Claude uses the time away (whatever they say, at most 1h30) to reread the notes, find real connections, read the pains and the projects, and test ideas in a throwaway place outside vault/. Only proposes, in vault/memory/corner/YYYY-MM-DD-<slug>.md - it does not assert, does not merge, does not push, does not install anything outside the throwaway, does not send messages to anyone. ORDER RULE - if the user asked for something before leaving, the request is done IN FULL first. TRIGGERS - "vou sair", "volto às X", "I'm heading out", "back at X", "/claude-corner". Do NOT trigger for a leave of a few minutes, for a specific task the user wants running, nor for deciding between two paths.
---

# claude-corner: the time away becomes a proposal

## Why it exists

While the user is away, the assistant sits idle, and the user comes back to the same point. That time can be
used to look at the collection calmly, and at what the user would not have done: cross notes that do not cite
each other, read the pains in a row, test a cheap idea. The risk is the assistant acting without the user. So the
product here is a **proposal with provenance**, never a decision.

## The rules

1. **The user's request comes first and whole.** If they said "do X and I'm leaving", I finish X, **check that
   it is done** and only then start the corner. If X cannot be finished without them, I say so right away and the corner
   does not start pretending it was finished.
2. **Only propose.** The only place to write is `vault/memory/corner/`. I do not touch `vault/notes/`,
   `profile.md`, `patterns.md`, `decisions.md` nor `vault/projects/`.
3. **Provenance on every finding.** File path and a short excerpt. The user's words go in quotation marks;
   an idea that was born mine carries the label **Claude's guess**.
4. **Test only in the throwaway.** A temporary directory (`mktemp -d`) or a worktree outside `vault/`.
   No merge, push, new remote, message sent, email, PR, nor installing a package outside the throwaway.
5. **Time has a ceiling.** Whatever the user says; with no stated deadline, **1h30**. If they come back earlier, I hand over what
   is ready.
6. **Link only if the file exists.** A full-path wikilink from `vault/`, in the middle of the argument. Never a
   `## Connections` block at the bottom.

> Talk to the user and write prose (notes, briefings, profile lines) in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, status values, paths, enums) stay exactly as written.

## The steps

### 0. Close the request and read the clock (you, Claude)

Apply rule 1. Then note the deadline (the time the user said, or 1h30 from now).

```bash
ls vault/memory/corner/ 2>/dev/null | tail -5
```

Open the previous proposals, so you do not repeat what the user already saw, adopted or declined.

### 1. Sweep the collection (you)

Each front yields **up to 5 findings**; read, do not write yet:

- **Connections:** notes from different areas that talk about the same thing and do not cite each other
  (`ls vault/notes/`, `grep -rli "<term>" vault/notes/`).
- **Pains:** `vault/memory/ideas/_pains.md`. Which ones repeat? Does any have a cheap remedy?
- **Projects:** `vault/projects/_index.md` and the roots. What is stalled and can be moved ahead as a proposal?
- **Free:** one thing the user did not ask for and that you think is worth a look, marked as a guess.

If a front is empty (folder missing, no pains), write "empty front" in the file. Do not fill it.

### 2. Pick up to 3 ideas to test (you)

Cut the weak and the repeated. Keep the ones that can be tested in the time left.

### 3. Test in the throwaway (you)

```bash
T=$(mktemp -d) && echo "$T"   # everything runs in here, never in vault/
```

Run, measure, write the prototype there. Record **what ran, the output and the verdict** (worked, did not
work, could not measure). If you hit a decision that is the user's, write `ESCALAR: <reason>` and continue
with the rest.

### 4. Write the proposal (you)

`vault/memory/corner/YYYY-MM-DD-<slug>.md`. Opens with a **summary of up to 150 words** (the strongest findings).
Then each finding carries: what it is, where it came from (path + excerpt), the test, the verdict and the
state `open`. Create the folder only if it is missing, and only that one.

### 5. Report on return (you)

A short summary in the chat (up to 8 lines) and the file path. Ask which proposal the user wants to look at
first. Nothing is committed unless they say so, and there is never a push.

## How to tell it is worth it

The summary fits in 150 words and every finding has a path next to it. If, after a few rounds, everything
stays `open`, the corner is producing volume and not value: shrink the round.

## Never

- Start the corner before finishing the user's request.
- Assert something about the user, or save what they "probably" want.
- Merge, push, send a message, create a remote or install outside the throwaway.
- Create a skill or task: only propose.
