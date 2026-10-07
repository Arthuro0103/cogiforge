---
name: know-my-product
description: Interviews the user about their product, one question at a time, and fills the product brief of ONE project in vault/projects/<name>/product.md using only their own words (who uses it, the problem, what exists, what it is NOT, success metric, constraints). Collects pains voiced during the interview with the literal quote and the date, proposes a ranking by frequency and cost, and links each pain to a project or task. Claude proposes; nothing is written to memory before the user says "yes". TRIGGERS - "/know-my-product <project>", "understand my product", "fill the product brief", "collect my pains", "help me know my users", "what should I build first". Do NOT trigger to get to know the user themselves (that is onboard), to open or close a session (open-session, close-session), to answer a question from the notes (ask), nor to choose between two paths (that is a decision, not an interview).
---

# know-my-product: the workbench learns the product from the person who builds it

## Why it exists

Help that does not know the product is generic, and a product description written by the model is a guess
that later sessions read back as fact. The fix is an interview: the person answers, the file keeps their
words. The same interview collects the pains they voice, because a pain with a quote and a date is the only
kind that can be ranked. The flow is explained in `docs/PRODUCT-AND-PAINS.md`; what loads when, in
`docs/CONTEXT.md`.

## The rules

1. **One question per message.** The next one depends on the answer.
2. **Context before options.** One sentence on why you ask, then 2 to 4 concrete options
   (`AskUserQuestion`) with room for a free answer.
3. **A short answer is an answer.** "I don't know yet" is valid: write it as that. Do not insist or rephrase.
4. **Nothing deduced.** If you inferred something, ask. A cell with no answer stays empty.
5. **Verbatim only for what they typed.** If they clicked an option you wrote, record "chose option X", with no quotation marks.
6. **Propose, then wait for "yes"** before writing to `vault/memory/`. The brief file may be drafted in the
   chat first; save it only after they approve it.
7. **No project name, no run.** Ask which project (list `vault/projects/`). Never guess.
8. **No real names of third parties** in what you write. Use roles or handles.

> Talk to the user in the language the user writes in. Never translate a quote: verbatim quotes stay in the
> original language. Fixed tokens (frontmatter keys, status values, paths) stay as written.

## The steps

### 1. Before asking (you, Claude)

```bash
ls vault/projects/
cat vault/projects/<name>/instructions.md
cat vault/projects/<name>/product.md 2>/dev/null
cat vault/memory/ideas/_pains.md
```

If `product.md` already has answers, this is a review: say what it holds and ask what changed.

### 2. Interview along the brief (the order follows the conversation)

The fields are those of `vault/worksheets/product-brief.md`:

| field | possible opening |
|---|---|
| who uses it | "Who is the last person you can picture using this? A role is fine." |
| the problem | "What did that person say, or do, that made you start this?" |
| what exists | "What do they use today when this does not exist?" |
| what it is NOT | "Name two things someone might expect from it that you will not build." |
| success metric | "What would you see, and by when, to say it worked?" |
| constraints | "What cannot change: time, money, tools, rules?" |
| first version | "What is the smallest thing that would help one real person?" |

If they already have an audience in mind, offer `vault/worksheets/audience.md` after the brief, not before.

### 3. Collect pains as they appear (you)

Whenever the user quotes someone, or says something hurts, write it down in the chat in this format and keep
going with the interview:

```
YYYY-MM-DD | "verbatim quote" | <source: who or where> | <frequency, if said>
```

Do not ask "is that a pain?" about everything. A pain needs a quote; if you only have your reading of it,
say so and ask for their words.

### 4. Draft the brief (you, with the user's yes)

Show `projects/<name>/product.md` as a draft with the answers in the sheet's fields, frontmatter
`type: product-brief` and `status: in-progress`, and a link to the project root. Ask *"can I save it like
this?"*. Save only after the yes.

### 5. Propose the ranking (you)

List the collected pains with quote, date and source; sort by frequency, then cost (use what they said, not
estimates). Mark each pain with its target: `project::<name>`, `task::`, `question::` or `none`.
Show it all, then ask which lines to append to `vault/memory/ideas/_pains.md`. Append **only the
approved ones**, at the end, in the queue's format `date | verbatim quote | source`.

### 6. The close (you)

One short message: the first thing the pains suggest building or testing, with the quote that supports it,
and what the log is too thin to say. Point to `docs/PRODUCT-AND-PAINS.md` for how to ask follow-up questions.
Do not start building.

## Never

- Write about the product or the user something they did not say.
- Save to memory before the "yes", or "clean up" their words.
- Rank a pain that has no quote.
- Judge the idea. The skill records and ranks; it does not grade.
- Write to `vault/notes/`, `patterns.md` or `decisions.md`.
