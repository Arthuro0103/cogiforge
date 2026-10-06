---
name: task-observer
description: Observes a work session and ONLY PROPOSES process improvements, appending to vault/memory/observations.md (date, what was seen, what is proposed). Looks for three signals - a skill that was missing, a step repeated three times, a correction the user made twice. Never writes to profile.md, patterns.md, decisions.md nor vault/notes/, and never creates a skill: the skill agenda belongs to the user, and adapt-skill guides the creation. It is the "improves with me" half of the workbench. TRIGGERS - "/task-observer", "observa essa sessão", "what do I repeat a lot?", "what could be automated?", "is there anything to improve in my process?". Do NOT trigger to carry out the task itself, to close the day (that is close-session), nor to create a skill (that is adapt-skill).
---

# task-observer: see the process while it happens

## Why it exists

Someone who always works the same way stops seeing their own way: the step repeated every day, the
correction given to the assistant for the third time, the skill that would help and nobody wrote. Whoever does
the work is too busy to take notes. Someone from outside has to look and **only point**, without touching.

## The rules

1. **Only propose.** The only file this skill writes is `vault/memory/observations.md`, and only
   by **appending** at the end. It never rewrites or deletes an earlier line.
2. **Three signals, nothing else.** (a) a skill that was missing, (b) a step done by hand 3 times or more,
   (c) a correction the user made 2 times or more. Without the number, it does not become an observation.
3. **Every observation brings its evidence.** Where it happened (file, date or a short excerpt of what was said) and the
   count. "It seems that..." without evidence does not go in.
4. **No claims about the user.** I write "step X appeared 3 times", never "they are disorganized".
   `profile.md`, `patterns.md` and `decisions.md` are claims about the user: I do not write there.
5. **Never create a skill.** If the signal is "a skill was missing", the observation says so and points to `adapt-skill`.
   The user decides if and when.
6. **Do not touch `vault/notes/`.** A note belongs to the user's collection.
7. **Observing does not interrupt.** Do not stop the work to comment; record it and show it at the end, or when asked.

> Talk to the user and write prose (notes, briefings, profile lines) in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, status values, paths, enums) stay exactly as written.

## The steps

### 1. Before (you, Claude)

```bash
tail -30 vault/memory/observations.md 2>/dev/null
```

Read what was already observed, so you do not repeat it. If an old observation happened again, **cite its date**
and add to the count instead of opening another one.

### 2. During the session (you)

Keep a simple mental count of: repeated commands or steps, corrections the user made
("no, not like that", "again", "I already told you"), and requests that had no skill to serve them. Note the
evidence on the spot, in two lines, so you do not depend on memory at the end.

### 3. Filter (you)

At the end of the block of work, discard what does not match the three signals or has no count. Keep
at most **3 observations per session**: more than that is noise, and the user stops reading.

### 4. Append (you)

If `vault/memory/observations.md` does not exist, say it belongs to the structure and show the
observations in the chat, without creating the file. If it exists, append at the end:

```markdown
## YYYY-MM-DD

- **What I saw:** <fact, with the count and where it happened>
- **Signal:** missing skill | repeated step | repeated correction
- **What I propose:** <one sentence; if it is a skill, "take it to /adapt-skill">
- **State:** open
```

If the observation concerns a project, put a full-path wikilink in the sentence, in the middle
of the text (`[[projects/<name>/instructions|<name>]]`), and only after checking that the file exists.

### 5. Show (you)

Chat: the day's observations in one line each, and the question *"is any of these worth turning into something?"*. If the
answer is about a skill, hand over to `adapt-skill`; do not start writing.

### 6. Close the cycle (the user)

Only the user changes the **State** field (`open`, `adopted`, `declined`). Declining is a good answer:
in the next round, do not propose the same thing again without a new count.

## Never

- Write to `profile.md`, `patterns.md`, `decisions.md` or `vault/notes/`.
- Create, edit or install a skill.
- Record an observation without a count and evidence.
- Repeat a proposal the user declined, without a new fact.
