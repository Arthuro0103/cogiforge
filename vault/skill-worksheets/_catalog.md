---
type: explanation
status: in-progress
---

# The catalog says what to look at, adapt or decline

Each line has a **worksheet** that explains the skill from the inside, without the author's collection. Reading a
worksheet takes about 10 minutes. `/adapt-skill` guides you through it and through one question that decides
everything: **does this solve a pain of yours?** Declining is a legitimate answer and is recorded in
`vault/memory/skills-reviewed.md`.

Before anything else, read [[skill-worksheets/anatomy-of-a-skill|the anatomy of a skill]] (5 minutes).

| skill | what it does, in one line | worksheet | can it be adapted now? |
|---|---|---|---|
| `council` | runs a costly decision through several angles that disagree and closes with a verdict | [[skill-worksheets/council\|council]] | yes, it is only method |
| `article` | takes a thesis to text with no invented citation: gap declared, source marked | [[skill-worksheets/article\|article]] | yes, if you write texts with sources |
| `product-idea` | finds real pain in what you already wrote and returns an idea, always with the quote of the pain | [[skill-worksheets/product-idea\|product-idea]] | yes, if you have written material to scan |
| `consult-notes` | answers a practical question only with what your notes say, citing the note behind each claim | [[skill-worksheets/consult-notes\|consult-notes]] | yes, if you have notes on the subject |

**Examples already written, for free.** The skills `open-session`, `close-session`, `task-observer`,
`claude-corner`, `adapt-skill` and `onboard` are in `.claude/skills/`. Read the `description` of one and
compare it with the anatomy: it is an example of a finished skill and a format reference.

## How to use

Run `/adapt-skill`. It asks one thing at a time, starts from what you already told it about yourself, and
ends with the skill written and tested by you, or with a "does not fit, because..." on record. In both
cases you learned the part that matters.
