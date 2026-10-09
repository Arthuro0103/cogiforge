---
type: explanation
status: in-progress
---

# The catalog says what to look at, adapt or decline

Each line has a **worksheet** that explains the skill from the inside, without the author's collection. Reading a
worksheet takes about 10 minutes. `/cf-adapt-skill` guides you through it and through one question that decides
everything: **does this solve a pain of yours?** Declining is a legitimate answer and is recorded in
`vault/memory/skills-reviewed.md`.

Before anything else, read [[skill-worksheets/anatomy-of-a-skill|the anatomy of a skill]] (5 minutes).

| skill | what it does, in one line | worksheet | can it be adapted now? |
|---|---|---|---|
| `council` | runs a costly decision through several angles that disagree and closes with a verdict | [[skill-worksheets/council\|council]] | yes, it is only method |
| `article` | takes a thesis to text with no invented citation: gap declared, source marked | [[skill-worksheets/article\|article]] | yes, if you write texts with sources |
| `product-idea` | finds real pain in what you already wrote and returns an idea, always with the quote of the pain | [[skill-worksheets/product-idea\|product-idea]] | yes, if you have written material to scan |
| `consult-notes` | answers a practical question only with what your notes say, citing the note behind each claim | [[skill-worksheets/consult-notes\|consult-notes]] | yes, if you have notes on the subject |

**Five skills that come with a template instead of a worksheet.** They are already in `.claude/skills/`;
each one fills a model (`cf-study` fills two, `cf-brand` four) that you copy into your project. Copy the model, never edit it here.

| skill | what it does, in one line | model it fills |
|---|---|---|
| `cf-extract-routine` | interviews you, one question at a time, and writes down a routine another person can follow | [[skill-worksheets/routine-template\|routine-template]] |
| `cf-brainstorm` | turns a loose idea into three different paths, a comparison you weigh, and a brief you approve before anything is built | [[skill-worksheets/brainstorm-brief-template\|brainstorm-brief-template]] |
| `cf-whats-real` | keeps the list of what works (with proof), what is simulated and what is unknown, before and after a milestone | [[skill-worksheets/whats-real-template\|whats-real-template]] |
| `cf-study` | interviews you about what and how you like to learn, plans small blocks, tests you by recall and marks an item mastered only after a retest on another day | [[skill-worksheets/study-plan-template\|study-plan-template]] and [[skill-worksheets/mastery-template\|mastery-template]] |
| `cf-brand` | interviews you, one question at a time, and keeps your voice rules, a project's DNA, messaging and design system in your words; the manual only assembles them and marks what is empty | [[skill-worksheets/brand-voice\|brand-voice]], [[skill-worksheets/brand-dna\|brand-dna]], [[skill-worksheets/brand-messaging\|brand-messaging]] and [[skill-worksheets/brand-design\|brand-design]] |

**Examples already written, for free.** The skills `cf-open-session`, `cf-close-session`, `cf-task-observer`,
`cf-claude-corner`, `cf-adapt-skill` and `cf-onboard` are in `.claude/skills/`. Read the `description` of one and
compare it with the anatomy: it is an example of a finished skill and a format reference.

## How to use

Run `/cf-adapt-skill`. It asks one thing at a time, starts from what you already told it about yourself, and
ends with the skill written and tested by you, or with a "does not fit, because..." on record. In both
cases you learned the part that matters.
