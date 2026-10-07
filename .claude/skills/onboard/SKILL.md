---
name: onboard
description: Workbench onboarding. Asks questions that follow what the user answered, one at a time, and the output comes from their own words - fills vault/_questions_about_me.md and proposes lines for vault/memory/profile.md with a date and a verbatim quote. Deduces nothing the user did not say; a short answer is a valid answer, and so is "prefer not to say". TRIGGERS - "/onboard", "primeira vez aqui", "atualiza meu perfil", "get to know me", "how do I use this workbench". May be suggested (never imposed) when vault/memory/profile.md is empty or missing. Do NOT trigger to open a project session (that is open-session), to get to know anyone other than the person using it, nor to research the user outside their own files.
---

# onboard: the workbench learns who uses it

## Why it exists

A workbench that really helps needs to know what the user uses it for: work, school, personal life,
projects. A profile copied from a template is useless; it only works when it comes from **real answers**,
and the good answers come from questions that follow what the user just said.

## The rules

1. **One question per message.** Never a list. The next one depends on the answer.
2. **Context before options.** One sentence saying why you ask, then 2 to 4 concrete options
   (`AskUserQuestion`), always with room for a free answer.
3. **Small questions.** "What is the last thing you finished and liked?" works. "What are your life
   goals?" stalls.
4. **A short answer or a refusal is an answer.** Do not insist, do not rephrase the same question. Note it and move on.
5. **Only the user's words go into the profile.** My assumptions do not go in. If I deduced something, I ask.
6. **Verbatim quote only for what they typed.** If they clicked an option I wrote, I record
   "chose option X", without quotation marks.
7. **8 to 15 questions.** Stop earlier if the blocks below are already covered.
8. **Nothing about health, family or relationships**, unless the user brings it up and asks to record it.

> Talk to the user and write prose (notes, briefings, profile lines) in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, status values, paths, enums) stay exactly as written.

## The steps

### 0. Shared mode (only if `vault/roles.txt` exists)

Find who is talking: `git config user.email`, matched against `vault/roles.txt`. If there is no line, stop and say
they must ask an admin to add one. Otherwise ask which handle they want to be called by only if the line is
ambiguous, and from here on use `vault/people/<handle>/memory/` wherever this skill says `vault/memory/`
(and `vault/people/<handle>/_questions_about_me.md` is not created: answer in the chat). Never open another person's folder.

### 1. Before asking (you, Claude)

```bash
cat vault/_questions_about_me.md 2>/dev/null
cat vault/memory/profile.md 2>/dev/null
ls vault/projects/ 2>/dev/null
```

If the profile already has lines, this is a review: open by saying what it says and ask what changed. If
`_questions_about_me.md` does not exist, say it belongs to the workbench structure and answer in the chat.

### 2. Talk through the five blocks (the order follows the conversation)

| block | what to find out | possible opening |
|---|---|---|
| **what for** | work, school, personal; what they want to organize first | "which of these areas weighs on you most today?" |
| **what they already do** | what works today, which tool they use, what they dropped | "what do you already write down or organize, and where?" |
| **where they get stuck** | starting, finishing, deciding, remembering | "when a project of yours stopped, where did it stop?" |
| **how they want help** | step by step or just the direction; nudging or autonomy | 3 concrete options |
| **how they want to use the workbench** | every day or only sometimes; short or detailed summaries | "what would make you open this tomorrow?" |

Someone who arrives with nothing to organize spends more time on **what for** and **where they get stuck**.

### 3. Fill in `_questions_about_me.md` (you, with the user's yes)

Show the answers organized by the file's questions and ask *"can I save it like this?"*. Save only
after the yes, keeping the user's words. A question without an answer stays blank.

### 4. Propose profile lines (you)

Build the lines and show them **before saving**, in this format:

```
YYYY-MM-DD | "verbatim phrase from the user" | <block> | <what this seems to say, marked as my reading>
```

If `vault/memory/profile.md` exists, append **only the lines the user approved**, at the end. If it does
not exist, leave the lines in the chat and say the file belongs to the structure.

### 5. The close (you)

One short message: which skills fit what the user said (`open-session` if they get stuck starting,
`close-session` if they lose the thread between days), one line each, with the user's phrase that supports it.
A skill of their own only if they described something they repeat; then point to `adapt-skill` and **do not create it**.

## Never

- Write into the profile something the user did not say, or "clean up" their words.
- Save without showing first.
- Judge the person: the profile describes, it does not grade.
- Write to `patterns.md`, `decisions.md` or `vault/notes/`.
