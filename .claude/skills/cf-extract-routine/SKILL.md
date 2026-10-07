---
name: cf-extract-routine
description: Pulls a real routine out of the user's head by interview and writes it down so someone else can run it. One question at a time, context before options, a short answer is valid. Covers expected result, trigger, inputs, steps in real order, decisions, exceptions, who does it and proof of done. Unknowns are marked [CONFIRM]; the agent never invents a step. States - draft, ready-for-human-review (the most the agent may declare) and validated (only after a SECOND person follows it without guessing, name and date recorded). Output is vault/projects/<name>/routines/<routine>.md. TRIGGERS - "/cf-extract-routine", "write down how I do X", "document this process", "how do I hand this over", "turn this into a checklist". Do NOT trigger to run the routine, to invent a process the user lacks, to choose between ways of working (that is a brainstorm), nor to record a one-off event (that is the diary).
---

# cf-extract-routine: get the routine out of one head and onto one page

## Why it exists

Most routines live only in the head of the person who does them. They work until that person is away,
tired or gone, and then nobody knows the order, the exceptions or how to tell it is done. The fix is a
page that a second person can follow. The hard part is not writing, it is **getting the real routine**,
not the tidy version people describe when asked "how does it go?". You are the interviewer: the content
belongs to the user.

Template: [[skill-worksheets/routine-template|routine-template]]. Copy it, do not edit it.

## The rules

1. **One question per message.** The next question depends on the answer.
2. **Context before options.** One sentence saying why you ask, then 2 to 4 concrete options
   (`AskUserQuestion`), always with room for a free answer. A short answer is a valid answer.
3. **Real order, not ideal order.** Ask "what do you do first, the last time you did it?", not "what are the steps?".
4. **Never invent a step.** Anything the user does not know, is unsure of, or answers "depends" without
   saying on what, is written as `[CONFIRM] <the open question>` in place of content.
5. **Their words stay.** If a step was said in a particular way, keep the phrase; do not polish it into jargon.
6. **The agent may never write `validated`.** The highest state it can set is `ready-for-human-review`.
7. **Read the page back** before saving: show it, ask "can I save it like this?", save only after the yes.

> Talk to the user and write the routine in the language the user writes in. Fixed tokens (frontmatter keys,
> status values, paths) stay exactly as written.

## The eight things to find out

| block | what to find out | possible opening |
|---|---|---|
| **expected result** | what exists in the world when the routine is done | "when this goes well, what is different afterwards?" |
| **trigger** | what starts it: a date, an event, a message, a feeling | "what made you do it the last time?" |
| **inputs** | what must be at hand before step one | "what do you open or need in front of you?" |
| **steps, in order** | the sequence as it really happens | "the last time, what was the very first thing you did?" |
| **decisions** | where the path forks and what decides it | "at any point did you stop to choose? between what?" |
| **exceptions** | what goes wrong and what you do then | "what is the usual thing that breaks it?" |
| **who** | who does each step, who can replace them | "does anyone else ever do a part of it?" |
| **proof of done** | how anyone can tell it finished | "how would someone else know it is over?" |

Start with the expected result and the trigger; the rest follows the conversation. Someone who cannot
name the proof of done has found the first `[CONFIRM]`, and that is a good result, not a failure.

## The steps

### 1. Before asking (you)

```bash
ls vault/projects/ 2>/dev/null
ls vault/projects/<name>/routines/ 2>/dev/null
```

If the routine already has a file, this is a review: read it, say what state it is in, and ask what changed.
If the project does not exist, ask which project root it belongs to; do not create the project here.

### 2. Interview (you and the user)

Walk the eight blocks. Keep a running draft in your head, never a long list shown to the user mid-way.

### 3. Write the page (you, with the user's yes)

Copy the template to `vault/projects/<name>/routines/<routine>.md`. Fill the frontmatter
(`type: routine`, `status: draft`, `owner`, `date`). The body must link the project root by full path
(`[[projects/<name>/instructions|<name>]]`), only after checking that file exists. Every unknown stays `[CONFIRM]`.

### 4. Move to `ready-for-human-review` (you)

Only when no `[CONFIRM]` blocks a step from being run in order, or when each remaining one is labelled as
non-blocking. Say which `[CONFIRM]` are left. Then stop: this is as far as you go.

### 5. Validate with a second person (a human, not you)

`validated` needs a second person, different from the owner, to read the page and follow the order
**without asking the owner and without guessing**. Use the pair QA checklist at the end of the template.
Only after it passes, record who and when in the page, and only then change the status. If the user says
"it is validated", ask for the name and the date before writing the word.

### 6. Run the gate

```bash
python3 core/gate.py
python3 core/ring.py --vault vault --gate
```

## The output

`vault/projects/<name>/routines/<routine>.md`, `type: routine`, with the project link in the body. Checked by the
gate (links resolve) and the ring (the file is connected).

## Never

- Fill a step, a decision or an exception the user did not say.
- Declare `validated`, or write a validator name that the user did not give you.
- Ask several questions in one message, or rephrase a question the user already answered shortly.
- Turn the real order into a better order. If the real order looks wrong, say so after, as a note, not in the steps.
