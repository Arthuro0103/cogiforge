# Studying with the workbench

Learn what you want, the way you want. You choose the topic and the way (reading, practising, examples, quizzes,
teaching it back, drawing or mapping, talking). Claude explains, asks you questions, and keeps a log of what you
actually proved you know. It does not learn for you.

## How to ask

```
/cf-study <topic>
```

Claude asks one question at a time: what you want to learn, why, by when (or no deadline), how you like to learn,
and how much time you have per day. Then three level questions to find your starting point. There is no grade,
and "I don't know" is a valid answer that gets written down. Then it writes two files in
`vault/projects/<topic>/`: `study-plan.md` and `mastery.md`.

## Three scenarios

**Studying for an exam.** Say the exam date and what it covers. The plan splits the content into small blocks
in order. Each session: Claude explains a block your way, then asks you questions with the material closed.
Ask for a retest the next day, so you see what stayed.

**Learning a skill.** Say what you want to be able to do. Choose practising as the way: Claude gives small tasks and
asks you to describe what you did and why, and the log keeps your words.

**Learning a topic out of curiosity.** No deadline needed. Pick the way that is fun: examples, conversation, a
map you draw. Change it whenever you like; the change is noted in the plan and it is not a failure.

## How the retest works

Every item starts as `learning`. It becomes `mastered` only when you answer it again, in a different session on a
different day, and the answer is logged in your own words. Answering well on the same day it was learned does not
count. A failed retest stays `learning` and the attempt stays in the log.

## What Claude does not do

- It does not do your homework or answer the recall question for you. Hints yes, answers no.
- It does not say you know something unless `mastery.md` has the proof and the dates.
- It does not invent sources, quotes or figures. What it explains without a source is marked `[VERIFY]`; check it
  in an open source before relying on it.

## Active-learning tips

- Recall before rereading: try to answer with the material closed, then check. [VERIFY 2026-10-07: general claim
  from learning research, not checked against an open source in this repo]
- Spread practice over several days instead of one long session. [VERIFY 2026-10-07: same, no source confirmed]
- Explain it back in your own words, as if to someone who does not know it. [VERIFY 2026-10-07: same, no source confirmed]
- No study numbers are given here on purpose: we have not confirmed any in an open source.

## For teachers

- **Set the goal.** Write what must be known and by when. The student chooses the way and the plan records that
  you set the goal.
- **See the progress.** Open each student's `mastery.md`: dates, states and the student's own words as proof. If
  team mode is enabled, each student has a folder in `people/<handle>/` and the files live there.
- A `mastered` item is one that passed a retest on another day. Anything else is `learning`.
