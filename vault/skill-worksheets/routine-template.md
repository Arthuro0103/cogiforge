---
type: routine
status: draft
owner: <who does this routine>
date: YYYY-MM-DD
---

# Template: a routine another person can follow without asking

Copy this file to `vault/projects/<name>/routines/<routine>.md`. Replace the title with a statement of up to ten words.
Delete this paragraph. Anything unknown stays as `[CONFIRM] <the open question>`; never fill a gap with a guess.

Project root: link it here with its full path, in the middle of a sentence, for example "this routine serves
`[[projects/<name>/instructions|<name>]]`". Check the file exists first. This line is the connection that keeps the page
from being an orphan. The skill that fills this template is described in `.claude/skills/extract-routine/SKILL.md`.

## Expected result

What exists in the world when this is done.

## Trigger

What starts it: a date, an event, a message.

## Inputs

What must be at hand before step one.

## Steps, in the order they really happen

1. First step, with who does it.
2. Second step.

## Decisions

| where | the choice | what decides it |
|---|---|---|
| after step N | A or B | `[CONFIRM]` |

## Exceptions

| what goes wrong | what to do |
|---|---|
| the usual breakage | the usual fix |

## Who

Who does each step, and who can replace them.

## Proof that it is finished

How anyone can tell, without asking the owner.

## States

- `draft`: being written, may have blocking `[CONFIRM]`.
- `ready-for-human-review`: the most an agent may declare. Nothing blocks running it in order.
- `validated`: a second person followed it without guessing. Record below.

Validated by: `<name>` on `<YYYY-MM-DD>`. Leave empty until it happened.

## QA in pairs (the second person does this, the owner stays silent)

- [ ] The reader is not the owner.
- [ ] The reader followed every step in order and never asked the owner what to do next.
- [ ] The reader never had to guess what a word, a tool or a place meant.
- [ ] Every decision could be taken from what the page says.
- [ ] Every exception had a written action.
- [ ] The reader could say, from the page alone, when it was finished.
- [ ] No `[CONFIRM]` is left, or each left is explicitly non-blocking.
- [ ] The place where the reader hesitated is written down, and the page was changed there.
