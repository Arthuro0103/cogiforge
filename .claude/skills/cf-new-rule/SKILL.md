---
name: cf-new-rule
description: Turns ONE real mistake of the user's into a rule that is justified, checked and tested. Interviews one question at a time (what happened, the date, the number), asks which check should have caught it, then builds in order - a pair of inputs (one that must fail, one plausible that must pass), a test that goes RED without the rule, the rule, a mutation entry, and a WHY.md entry. Refuses a rule with no dated mistake behind it and a test that has never been seen red. Writes outside vault/ only after the user says yes in this session. TRIGGERS - "/cf-new-rule", "turn this mistake into a rule", "this keeps happening, make it a rule", "add a rule for", "it passed and it should not have". Do NOT trigger for a mistake that has not happened yet ("it could happen": that is not enough), to record a preference of the user (that is cf-task-observer, which only proposes), to write a skill (that is cf-adapt-skill), nor to find out whether something works (that is cf-whats-real).
---

# cf-new-rule: a mistake in, a rule with a test out

## Why it exists

A rule written from a fear is a rule nobody can check. The rules that last in this repo each came from a
mistake with a date and a number, and each has a test that goes red without it ([WHY.md](WHY.md)). This skill
walks the user through that order, so the rule is written **last**, after the proof that it is needed.

## The rules

1. **One question per message.** Context first (one sentence on why you ask), then the question, and room for a
   free answer. A short answer is a valid answer.
2. **No mistake, no rule.** It needs a date and a number or a quote: "on Sep 5, 7 of 8 checks could be deleted". "It
   could happen" does not enter. If the user has no date, record it as `[CONFIRM]` and stop there.
3. **Nothing is deduced.** What happened, the date and the number come from the user's mouth or from a file you
   opened and quoted. Never invent an incident, a figure or an example to make the rule look justified.
4. **The test comes before the rule.** Write the failing input, run it, and show it red. A test never seen red tests
   nothing. Then write the rule and show it green.
5. **A pair, always.** One input that must fail **and** a plausible one that must pass. A check that fails on
   everything passes the first and breaks the user's real work.
6. **Never write outside `vault/` on your own.** Tests, `WHY.md`, `CLAUDE.md`, `AGENTS.md` and `core/` change only
   after the user says, in this session, "yes, write it there". Without that "yes" the draft stays in the chat.
7. **`CLAUDE.md` stays under 5 KB.** Measure before and after (`wc -c CLAUDE.md`). If the new line would cross it,
   say so and propose which rule to shorten; never drop a rule silently.
8. **Never claim a rule is enforced if no test fails without it.** Say `NOT_VERIFIED` and why.
9. **Never use `--no-verify`** to get the new rule past the hook.

## The steps

### 1. The mistake (the user)

Ask, one at a time:

1. What happened? (Their words; you quote them.)
2. When? (Date, or "I don't remember": `[CONFIRM]`.)
3. What was the number, or the exact thing you saw? (A count, a file, a message.)
4. What did the tools say at the time? (OK, silent, a wrong message.) This is the gap the rule has to close.
5. What should have happened instead, in one sentence?

Read the existing rules first, so you do not write one twice:

```bash
grep -n "^### " WHY.md
```

If the mistake matches an entry, say which and ask whether to extend it instead.

### 2. Which check catches it (you and the user)

Name the place where the catch belongs, from what exists: `core/gate.py`, `core/ring.py`, `core/leak.py`, a hook
step, a skill step, or **none**. If none, say the rule would be a sentence nobody checks, and ask whether the
user wants a new check or to drop the rule. Do not build a new check unprompted.

### 3. The pair and the red test (you)

Write the two inputs in a scratch folder (never in `vault/`): the one that must fail and the plausible one that
must pass. Write the test, run it **without** the rule, and show the red output.

```bash
python3 -m pytest -q tests/test_<name>.py
```

### 4. The rule (you)

Write the smallest change that turns the test green, run it again, and show the green output. Then run the whole
suite and report the counts as they appear.

### 5. The mutation (you)

Add an entry in `tests/mutate.py` that breaks the new check, and run `python3 tests/mutate.py --dry` and then the
mutation of that piece. A mutant that stays alive means the test is not good enough: go back to step 3.

### 6. The record (you, with the user's "yes")

Show the `WHY.md` entry in the same shape as the others: **What broke** (the user's dated mistake, no project
names), **The rule**, **Who catches it**, **The test**. Show the one-line `CLAUDE.md` rule and its size. Ask:
"Write these in the repo? (yes/no)". Only on "yes", write them, and keep `AGENTS.md` in step with `CLAUDE.md`.

### 7. Run the gates

```bash
python3 core/gate.py
python3 core/ring.py --vault vault --gate
python3 core/leak.py .
python3 -m pytest -q
```

Report each rc. Say "done" only after they ran.

## The output

A test that goes red without the rule, the rule, a mutation entry and a `WHY.md` entry, all written only after the
user's "yes". If any step could not be proven, the output says `NOT_VERIFIED` and which.

## Never

- Write a rule from a mistake that has not happened, or from an example you made up.
- Write the rule before the red test, or call a test good without having seen it red.
- Edit `core/`, `tests/`, `WHY.md`, `CLAUDE.md` or `AGENTS.md` without the user's "yes" in this session.
- Let `CLAUDE.md` grow past 5 KB without saying so.
- Bypass the hook to commit.
