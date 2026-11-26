---
name: cf-help
description: Explains which workbench skills to use and how, tailored to what the user said about themselves. Reads the profile and counts what exists in the vault; short route in chat, detail on request. Writes nothing. TRIGGERS - "how do I use", "which skill", "what can I do here", "como uso", "qual skill", "me ajuda a usar". Do NOT trigger when a concrete task is already asked (that task's skill).
---

# cf-help: which skill, for you, now

## Why it exists

A workbench with many skills is a menu, and a menu does not say what to order. The answer depends on the person:
what they said they want, and what already exists in their vault. This skill reads both and answers short.

## The rules

1. **Read only.** Writes no file and makes no commit, not even a log of the question.
2. **Who the person is comes only from what they said**: the approved lines of `vault/memory/profile.md` (dated, with
   a verbatim phrase) and the answers in `vault/_questions_about_me.md`. Quote the phrase when you use it.
3. **Never deduce anything about the person** from a folder name, a note or a project. A project called "garden" does not
   say they like plants. If it was not said, it is not used.
4. **What exists is counted, not guessed** (step 2). "You already use X" and "this does not exist here yet" both come from a count.
5. **The skill list comes from the disk, right now**: `.claude/skills/*/SKILL.md`. This file holds no list of skills.
   What a skill does comes from its own `SKILL.md`. Never describe a skill from memory.
6. **At most one question before answering**, and only when the profile is empty (step 3).
7. **Simple words, in the language the person writes in.** Skill names, paths and commands stay as they are.

> Talk to the user in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, paths, commands) stay exactly as written.

## Which mode

- `/cf-help` with no argument: **route mode** (step 4).
- `/cf-help <skill>`: **detail mode** (step 5).

## The steps

### 1. Read the skills (you, Claude)

```bash
ls .claude/skills/*/SKILL.md
grep -h "^description:" .claude/skills/*/SKILL.md
```

Read the `description` of every skill. Open the whole `SKILL.md` only of the ones you will recommend or explain.
The README table "Who it is for" is a starting point (just you, studying, a team or a school), not a verdict.

### 2. Read the person and count what exists (you)

```bash
cat vault/memory/profile.md 2>/dev/null
cat vault/_questions_about_me.md 2>/dev/null
ls vault/projects/ 2>/dev/null
grep -l -E "^status: *(open|in-progress)" vault/tasks/*.md 2>/dev/null | wc -l
find vault/notes -name "*.md" 2>/dev/null | wc -l
ls vault/people vault/roles.txt 2>/dev/null
ls -t vault/memory/diary/*.md 2>/dev/null | head -1
ls vault/memory/briefings vault/memory/ask-log.jsonl vault/projects/*/study-plan.md 2>/dev/null
```

The profile "has lines" only for lines in the format `YYYY-MM-DD | "phrase" | ...`. The header and the format
explanation are not lines. In shared mode (`vault/roles.txt` exists), read `vault/people/<handle>/memory/` instead,
where `<handle>` comes from `git config user.email` matched in `roles.txt`, and never open another person's folder.

Traces of use are facts: a briefing means the day was closed before; an `ask-log.jsonl` means questions were asked;
a `study-plan.md` means studying has started; a diary file has a date. Use them to say "you already use X" or
"this does not exist here yet". A missing trace is not a judgment of the person.

### 3. Empty profile (you)

If the profile has no lines and the answers file is blank, say so in one line and recommend `/cf-onboard` first.
Then offer to answer now from a single question: *"What do you want to do here first?"* (context in one sentence,
free answer allowed). Answer from that one reply, quoting it, and ask nothing else.

### 4. Route mode (you)

The answer has four parts, in this order:

1. **What I read**, one line: `profile: N lines; vault: N projects, N open tasks, N notes`, and the date of the last diary if there is one.
2. **For you, now**: 3 to 5 skills picked from what the person said and from what exists. For each one:
   - when to use it, tied to the quoted profile phrase or to the counted fact;
   - one sentence they could say, in their context, with a project name that really exists in `vault/projects/`
     (no project, no project name: say it generically);
   - what the skill writes, taken from its `SKILL.md` ("nothing" if it only reads).
3. **The others**: every remaining skill in one line, from its `description`.
4. **More detail**: say that `/cf-help <skill>` explains one skill in full.

Keep it short. Whoever wants more asks for it. If the vault has `roles.txt` or `people/`, a team or school is
the context; say it as a count, not as a conclusion about the person.

### 5. Detail mode (you)

Open the whole `.claude/skills/<skill>/SKILL.md`. If the name does not exist, say so and list the closest names
from the disk; do not guess which one was meant. Then explain, in this order:

1. what it is for;
2. when NOT to use it (its "Do NOT trigger", and which skill to use instead);
3. what the person will see, step by step;
4. what it writes and where;
5. two example sentences in the person's context (real project names only);
6. what it needs first (a file, another skill), checked against the counts of step 2.

## Never

- Write, edit or commit anything.
- Say something about the person that they did not say.
- Describe a skill without opening its `SKILL.md`, or recommend one that is not on the disk.
- Ask more than one question before answering.
- Run the skill you are explaining: explain it and let the person ask for it.
