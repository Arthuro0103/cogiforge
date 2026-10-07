---
type: worksheet
status: in-progress
---

# Worksheet: product-brief, what you are building, for whom, and what it is not

## When to use it

When you start a project that makes something for someone (an app, a service, a course, a school
project with a "client"), and again whenever the answer to one of these questions changes.
It is a one-page brief, not a business plan. Short answers are fine; "I don't know yet" is a valid answer.

## What Claude does with it

Claude interviews you one question at a time (the `cf-know-my-product` skill does this) and writes the
answers into `projects/<name>/product.md` **with your words only**. At the start of a session it reads
that file, so its suggestions fit your product instead of a generic one. Claude fills nothing you did not
say. The rules of the workbench are in [[CLAUDE]].

## Fields (copy this block into `projects/<name>/product.md`)

| field | question | your answer |
|---|---|---|
| who uses it | Who is the person, in one sentence? Name a real one if you can. | |
| the problem | What goes wrong for them today, in their words? | |
| what exists | What do they use now (a tool, a spreadsheet, nothing)? Why is it not enough? | |
| what it is NOT | Name two things people might expect from it that you will not do. | |
| success metric | How will you know it worked? One number or one observable event, with a date. | |
| constraints | Time, money, tools, rules, people. What can you not change? | |
| first version | What is the smallest thing that would help one real person? | |

## Rules for filling it

1. **One sentence per cell.** If it needs a paragraph, it is two cells.
2. **A quote beats a summary.** If someone told you the problem, paste what they said and the date.
3. **"What it is NOT" is mandatory.** A brief with no exclusions grows forever.
4. **Review it when a pain changes the answer.** Link the pain: see [[worksheets/pains]].

## Next

Who exactly is the user? Go deeper in [[worksheets/audience]]. What are you building and by when?
See [[worksheets/project-brief]]. The full flow is in [docs/PRODUCT-AND-PAINS.md](../../docs/PRODUCT-AND-PAINS.md).
