# Product and pains: how the workbench learns what you build and what hurts

Claude helps better when it knows two things: **what the product is** and **what actually hurts the people
who would use it**. Neither can be guessed. This guide shows the flow that collects both, in the person's
own words, and turns them into a decision about what to do first. It works for a personal project, a company
product or a school assignment.

## The flow in five steps

1. **Fill the product brief.** Run the `know-my-product` skill (or fill the sheet by hand). You answer; Claude
   writes **only your words** into `projects/<name>/product.md`. Sheet:
   [product-brief](../vault/worksheets/product-brief.md).
2. **Collect a pain in every conversation.** When someone says something hurts, the pain goes into
   `vault/memory/ideas/_pains.md` as `date | verbatim quote | source`. No quote, no line. Richer sheet:
   [pains](../vault/worksheets/pains.md).
3. **Rank the pains** by frequency first and cost second. Frequency is counted from the log, not guessed.
4. **Link each pain to a target.** A pain that feeds no project or task is a complaint, not a lead. Name the
   target first: `project::`, `task::`, `question::` or `none` (and `none` is a fine answer).
5. **Decide and log.** Write the choice in the [decisions-log](../vault/worksheets/decisions-log.md) with the
   alternatives and who can reverse it.

Claude proposes every step; you approve with "yes" before anything is saved to memory.

## What each file holds

| file | holds | written by |
|---|---|---|
| `vault/projects/<name>/product.md` | the product brief: who, problem, what exists, what it is NOT, metric, constraints | you, through the interview |
| `vault/memory/ideas/_pains.md` | the queue of pains, one per line, with the literal quote | Claude proposes, you approve |
| `vault/worksheets/pains.md` and `csv/pains.csv` | the long-form log with frequency, cost and what was tried | you |
| `vault/worksheets/audience.md` | who the work is for | you |
| `vault/worksheets/decisions-log.md` | what you decided and why | you, Claude proposes |

## Ranking pains

Use two columns and sort:

1. **How often** it happens (count entries and distinct people, not feelings).
2. **What it costs** (minutes per week, money, missed deadlines).

A pain heard from three different people beats a louder pain from one. A pain you invented does not rank:
it has no quote. If two pains tie, ask which one the person would pay, in time or money, to remove.

## How to ask for help with it

Once the brief and some pains exist, ask in plain words:

- "Based on my pains and the product brief, what should I build first?"
- "Which pain is the most frequent and cheapest to fix?"
- "Does this idea solve any of the pains I logged? Quote the one it solves."
- "What in my product brief contradicts what people said?"

A good answer cites the pain by date and quote, and says what it could **not** conclude because the log is
thin. If Claude answers without citing a logged pain, ask it to point to one, or say it does not know.

## If team mode is enabled

When the workbench is used by more than one person (a `people/<handle>/` folder per person and a `roles.txt`
that says who can see what), the split is:

| kind of pain | where it lives |
|---|---|
| **personal**: how one person works, what annoys them | in that person's own folder under `people/<handle>/` |
| **about the product**: what the users say hurts | in the project, `projects/<name>/` |

Nobody writes a pain into another person's folder. A personal pain becomes a product pain only when its owner
says so. If team mode is not enabled, everything stays in `vault/memory/` as described above.

## What it will not do

- It will not deduce a pain you did not voice, nor a user you did not describe.
- It will not rank pains without quotes.
- It will not save anything about you or your users without your "yes".

## Related

- [CONTEXT.md](CONTEXT.md): what loads when, and how to keep the context small and specific.
- [vault/worksheets/](../vault/worksheets/): all the sheets, with CSV versions of `pains` and `decisions-log`.
