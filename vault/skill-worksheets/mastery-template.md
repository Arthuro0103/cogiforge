---
type: mastery
status: in-progress
topic: <what the student is learning>
date: YYYY-MM-DD
---

# Template: the log of what was learned and what was proven

Copy this file to `vault/projects/<topic>/mastery.md`. Replace the title with a statement of up to ten words.
Delete this paragraph. One row per item. The agent writes a row only with the student's own answer as proof.

This log goes with the plan made from [[skill-worksheets/study-plan-template|study-plan-template]]. The skill that
keeps it is described in `.claude/skills/study/SKILL.md`.

## The two states

- `learning`: seen, tried, or answered once. Also every item that passed only on the day it was learned.
- `mastered`: answered again in a RETEST on a different day, with the proof written below.

No proof, no state change. A failed attempt is logged, never deleted.

## Log

| item | date | state | proof (the student's own words) | retest date |
|---|---|---|---|---|
| example item | YYYY-MM-DD | learning | what the student answered, verbatim | pending |

## Retest queue

Items still `learning` that were learned on an earlier day. Retest them first in the next session.

- example item
