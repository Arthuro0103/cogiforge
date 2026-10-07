---
name: cf-adapt-skill
description: Guides the user to make a skill of THEIR OWN from a catalog worksheet (vault/skill-worksheets/) - read the worksheet, separate the method from what belongs only to the original author, decide whether it solves one of their pains, write it with their answers, test it on a real case and record the verdict in vault/memory/skills-reviewed.md. One question per message. Claude never writes the skill alone, and "does not fit me" is a valid answer that gets recorded. TRIGGERS - "/cf-adapt-skill", "quero uma skill parecida com essa", "does this skill fit me?", "how do I make a skill", "what is in the skill catalog". Do NOT trigger to USE a skill that already exists, to create a skill without having looked at a worksheet, nor for cf-task-observer to propose a skill (it only points here).
---

# cf-adapt-skill: learn to make your own by looking at someone else's

## Why it exists

A skill handed over ready-made teaches how to **use** it. A skill the user decides on, writes and tests
teaches how to **make** one, and what fits changes from person to person: someone who writes a lot and
someone who writes code fight over different things. A skill with no pain behind it becomes decoration that
spends context in every session. Here, the worksheet is the material and the **user** is the author.

## The rules

1. **One question per message.** Never a list. Say in one sentence why you ask and offer 2 to 4
   concrete options (`AskUserQuestion`), always with room for a free answer.
2. **Claude does not write the skill alone.** The pain, the triggers and the "when NOT" come from the
   user's answers. I organize and format. If I deduced something, I ask.
3. **Teach while doing.** At each step, one sentence about what that part does in a skill, with the
   reference in `vault/skill-worksheets/anatomy-of-a-skill.md`.
4. **"Does not fit" is a good answer.** Record it with the why.
5. **No pain, no skill.** If the user cannot say when they did this by hand (or why they will need it), the answer is
   "not now": record it and the conversation ends well.
6. **A skill without a test is a hypothesis.** I run it on a real case before calling it ready.
7. **Only in the user's repo.** The new skill goes in `.claude/skills/<name>/` and never overwrites another one.

> Talk to the user and write prose (notes, briefings, profile lines) in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, status values, paths, enums) stay exactly as written.

## The steps

### 1. Before asking (you, Claude)

```bash
cat vault/skill-worksheets/_catalog.md
cat vault/memory/skills-reviewed.md 2>/dev/null     # what the user already looked at
head -40 vault/memory/ideas/_pains.md 2>/dev/null   # pains already collected
```

If `skills-reviewed.md` has lines, open by saying what the user already reviewed.

### 2. Choose which worksheet to read

Show the catalog in one line per skill. Ask if any caught their eye. If they ask for a suggestion,
propose **at most two**, each with the **user's phrase** (from `_pains.md`, the profile or the conversation)
that supports it, and say what you have not read enough to claim. Option "none fits today": record it
in step 7 and stop.

### 3. Read the worksheet together

Summarize the worksheet in 5 lines. Before showing the table, ask: *"in this skill, what do you think is only
the author's and what is method anyone would use?"* Then show the worksheet's table and say where they
got it right and where something was missing.

### 4. The pain

Ask: **"when was the last time you did this by hand?"** Ask for the concrete case and note the date.
The pain can be in the future if they say why; "it would be nice to have" does not count. With no pain, go to step 7 with
"not now". With a pain, continue.

### 5. Write, one part per message

Always the question first, the text after, taken from their answer:

1. **Why it exists:** *"what annoyed you, in one sentence?"*
2. **Triggers:** *"what phrases would you type to call this?"* (3 to 5, in their words)
3. **When NOT to trigger:** *"in what situation would this only get in the way?"*
4. **Steps:** for each step of the worksheet, *stays, goes or changes?* Each "changes" is something that depended on the
   author: ask what goes in its place.
5. **Output:** *"where is this saved and how do you know it came out right?"*
6. **Never:** *"what should this skill never do?"*

Name: the user chooses. `description` up to 1024 characters, with `TRIGGERS` and `Do NOT trigger` (check with
`wc -c`). Build the `SKILL.md`, **show it whole** and ask *"is this right? what would you take out?"*. Only
save `.claude/skills/<name>/SKILL.md` after the yes.

### 6. Test on a real case

Ask for a case from today, not an invented one. Run the skill with the user watching the output. Ask *"did it work? what
was missing? what was extra?"* and adjust **once**. With no case today, record "not tested".

### 7. Record

Append a line to `vault/memory/skills-reviewed.md` (if it does not exist, create it with the header only):

```markdown
| date | worksheet | verdict | pain cited | what changed | your skill |
|---|---|---|---|---|---|
| YYYY-MM-DD | council | fits, adapted | "I was stuck two days between A and B" | swapped the lenses | .claude/skills/<name>/SKILL.md |
```

Verdict: **fits, adapted** · **fits as is** · **fits later** · **does not fit**. The skill column
is filled in only if the file exists.

## The close

Ask the user to say, in their own words, what they learned about making a skill. Note the next case where
the skill should be used.

## Never

- Hand over the finished skill or write parts without a question.
- Create a skill without the user asking.
- Grade the user: the question is whether the **skill** fits, not whether they got it right.
- Copy the whole worksheet as if it were the user's skill.
