---
type: worksheet
status: in-progress
---

# Worksheet: pains, a log of what hurt, in the words of whoever said it

## When to use it

Whenever someone (you, a customer, a classmate, a teammate) says something is annoying, slow, confusing
or expensive. Write it down the same day. Do not wait for a pattern: the pattern only shows up after you
have ten of these.

## What Claude does with it

Claude collects pains from the conversation (the `cf-close-session` skill does it at the end of the day) and
appends them to [[memory/ideas/_pains]], the queue. This worksheet is the richer version of a queue line:
use it when a pain deserves the extra fields. Claude ranks pains by **frequency and cost** and links each
one to a project or a task. A pain without a verbatim quote does not enter the ranking.

## One row per pain

| field | what goes in it |
|---|---|
| date | When it was said (YYYY-MM-DD). |
| who said it | You, or a role ("a customer", "a teammate"). Use a handle or a role, not a real name, if the file will be shared. |
| verbatim quote | Exactly what they said. No paraphrase. |
| where it shows up | The place, step or screen where it happens. |
| frequency | How often: once, weekly, daily. Count, do not guess. |
| already tried | What they did about it, and why it did not work. |
| cost | What it costs: minutes per week, money, a missed deadline, an annoyed person. |
| linked to | The project or task this pain feeds: `[[projects/<name>/instructions]]`. |

## Example row (invented)

| date | who | quote | where | frequency | tried | cost | linked to |
|---|---|---|---|---|---|---|---|
| 2026-10-02 | a customer | "I copy the same numbers into three sheets every Monday" | weekly report | weekly | a macro, broke twice | 40 min/week | a project of yours |

## Ranking

Sort by **frequency first, then cost**. A daily pain that costs 5 minutes usually beats a yearly pain that
costs an hour. When two tie, the one with a quote from more than one person wins.

## Spreadsheet version

If you prefer Sheets or Excel, use `worksheets/csv/pains.csv`. To paste it back: export the sheet as CSV,
keep the header row, and append the new rows to that file. Then tell Claude "the pains CSV changed": it
reads the rows and proposes the lines for [[memory/ideas/_pains]]; nothing is saved without your "yes".

## Next

The flow around this is in [docs/PRODUCT-AND-PAINS.md](../../docs/PRODUCT-AND-PAINS.md). Whose pain it is:
[[worksheets/audience]]. What to build first: [[worksheets/product-brief]].
