---
type: explanation
status: in-progress
---

# A skill has seven parts and each has a function

A skill is a **folder with a `SKILL.md` file** in `.claude/skills/<name>/`. Claude Code reads the
`description` of **every** skill at the start of each session and only opens the body of the one that matches the request.
So two things matter a lot: the `description` decides **when** the skill triggers, and each line of it
**costs context in every session**, even in the ones where it never triggers.

To see it in practice, open `.claude/skills/cf-onboard/SKILL.md` alongside (the shortest one) and find each part.

## The seven parts

| part | what it is for | where to find it in `cf-onboard` |
|---|---|---|
| **1. `description`** | the trigger: what it does, the phrases that call it (`TRIGGERS`) and when **not** to fire (`Do NOT trigger`). At most 1024 characters | the frontmatter |
| **2. Why it exists** | the pain that originated the skill, preferably with the words of whoever felt it. Without pain, the skill is decoration | the "Why it exists" section |
| **3. The rules** | a few rules, each **verifiable**: you can tell whether it was followed or not | the "The rules" section |
| **4. The steps** | what to do, in order, with the real command, saying who does each step (the user, Claude, a script) | "The steps" |
| **5. The output** | where it writes, in what format, and how it is checked | the step that writes the profile |
| **6. The model of each agent** | only if the skill opens agents: which ones only read (smaller model) and which ones decide (larger model) | `cf-onboard` has none: it opens no agents |
| **7. Never** | what the skill does not do. It is the part that prevents the most damage | the "Never" section |

## What separates the skill that gets used from the one nobody calls

1. **The pain has a quote.** Test question: *when was the last time you did this by hand?* The pain can be
   past or **future**, if you say why you will need it. "It would be nice to have" does not count. Saying "I
   do not know if I have this pain" is also an answer.
2. **It was tested on a real case.** A skill written and not run is a hypothesis. Running it and looking at the output is half
   the work.
3. **The trigger is honest.** `Do NOT trigger` matters as much as `TRIGGERS`: a skill that fires for nothing
   annoys people and wastes context.
4. **It says what it depends on.** If it needs a file, a folder or an installed program, that goes
   at the top; otherwise whoever copies it takes a skill that fails silently.
5. **It can be deleted.** A skill that did not help goes away. "It did not help" is a good answer.

## Adapting is not copying

When you read someone else's skill, separate two layers:

- **The method**, which works for anyone: "the pain with a quote comes before the idea"; "check the fact before
  judging"; "several lenses that disagree with each other".
- **What belongs to the author**: their folders, their projects, their way of deciding, the tools they
  installed. You swap this for yours or cut it.

The question that drives adaptation: *"what in this skill only works because it is the author?"* Each answer becomes a
swap point. `/cf-adapt-skill` guides this work, and what you can look at is in
[[skill-worksheets/_catalog|_catalog]].
