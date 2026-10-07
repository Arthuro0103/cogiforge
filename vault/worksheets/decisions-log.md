---
type: worksheet
status: in-progress
---

# Worksheet: decisions-log, what you decided, why, and who can undo it

## When to use it

Each time you choose between two or more real options and the choice has a cost: a tool, a scope cut, a
deadline, a person. Skip it for trivial choices. The test: would you be annoyed to rediscover this in three
months without the reason?

## What Claude does with it

Claude reads the log before suggesting a change, so it does not reopen what you already decided. If a
suggestion contradicts a logged decision, it says so and asks. The latest decision on a topic wins over older
material. Claude proposes entries; they go in [[memory/decisions]] or the project root only with your "yes".

## One row per decision

| field | what goes in it |
|---|---|
| decision | One sentence, in the past tense: "We use X." |
| date | YYYY-MM-DD. |
| alternatives | What else was on the table. At least one. |
| why | Your reason, in your words. A quote if someone else gave it. |
| who can reverse it | A role or a handle, and under what condition. |
| revisit on | A date, or the event that should trigger a second look. |

## Example row (invented)

| decision | date | alternatives | why | who can reverse | revisit on |
|---|---|---|---|---|---|
| We start with a spreadsheet, not an app | 2026-10-03 | a small app; a form | "I want to test it with real people in a week" | the project owner | after 5 users |

## Spreadsheet version

Use `worksheets/csv/decisions-log.csv`. To paste it back: export as CSV, keep the header row, append the new
rows to that file, and tell Claude "the decisions CSV changed". It proposes the lines to add to your memory;
nothing is saved without your "yes".

## Next

Feed it from [[worksheets/project-brief]] and [[worksheets/weekly-review]]. A decision that came from a pain
should name the pain: [[worksheets/pains]].
