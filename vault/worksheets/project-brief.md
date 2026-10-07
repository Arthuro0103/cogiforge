---
type: worksheet
status: in-progress
---

# Worksheet: project-brief, the declared target, the date, the risk, and what decides

## When to use it

At the start of any project, and at every checkpoint where you wonder if you are still on track. It is the
short form of the project root: the part Claude needs to prioritize.

## What Claude does with it

Claude copies the answers into the frontmatter and sections of `projects/<name>/instructions.md`
(`declared_target`, the deadline row, the open questions). At the start of a session it reads them and checks
whether today's work moves the target. If your work and the target disagree, Claude asks; it does not
decide. See [[projects/example-my-first-project/instructions|the example project]] for the shape.

## Fields

| field | question | your answer |
|---|---|---|
| declared target | One sentence: what exists in the world when this succeeds? | |
| deadline | A date, or "no deadline" (and then say what would make you stop). | |
| biggest risk | The one thing most likely to make it fail. | |
| what decides | The fact or event that will tell you to continue, change or stop. | |
| next step | One concrete action, small enough for today. | |
| who is involved | Roles or handles. Who can say no? | |
| not now | What you decided to leave out for this round. | |

## Rules

1. **The target is a sentence about the world, not about your work.** "Ten students use it" beats "build the app".
2. **One risk.** If you list five you have not chosen.
3. **"What decides" needs a date or a number.** Otherwise it will never decide anything.

## Next

Product questions go in [[worksheets/product-brief]]. Log choices in [[worksheets/decisions-log]]. Check the week
with [[worksheets/weekly-review]].
