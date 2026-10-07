---
name: cf-whats-real
description: Keeps vault/projects/<name>/whats-real.md, a page with three sections - Works (each item with proof - the command run, its output and the date), Simulated or demo (what looks like it works and does not) and Unknown - plus a short dated diary.md for the project. It is created BEFORE a milestone (demo, delivery, class, launch) and CHECKED after it - every Works item needs its proof re-run, otherwise it goes back to Unknown. The agent never moves an item to Works without proof. TRIGGERS - "/cf-whats-real", "what actually works", "before the demo", "before I deliver", "what is real and what is fake", "check the whats-real after the launch", "what did we only simulate". Do NOT trigger to fix what is broken, to write the closing summary of a day (that is cf-close-session), nor to judge the quality of an idea (that is a brainstorm).
---

# cf-whats-real: separate what works from what only looks like it works

## Why it exists

Before a demo or a delivery, everything feels done. Afterwards, someone finds that half of it was a
mock, a hard-coded number or a path that only worked on one machine. The damage is not the missing part;
it is that nobody had said which part was missing. This page says it **before** the milestone, and the
check afterwards shows what the milestone really proved.

Template: [[skill-worksheets/whats-real-template|whats-real-template]]. Copy it, do not edit it.

## The rules

1. **Three sections, and only three.** `Works`, `Simulated or demo`, `Unknown`.
2. **No proof, no Works.** An item enters `Works` only with the command that was run, its output (or
   the relevant line of it) and the date. "I believe it works" goes to `Unknown`.
3. **Never move an item to Works without running the proof now.** Run it, paste what it printed.
4. **After the milestone, re-run every proof.** If it does not reproduce, the item returns to `Unknown`
   and the date of the failed re-run is written next to it. Never delete the line.
5. **Simulated is a result, not a shame.** A mock that is labelled is useful; a mock that is hidden is the problem.
6. **The diary is short and dated.** A few lines per entry: what changed, what was run.

> Talk to the user and write the page in the language the user writes in. Fixed tokens (frontmatter keys,
> section names, paths) stay exactly as written.

## The steps

### 1. Create, before the milestone (you and the user)

```bash
ls vault/projects/<name>/ 2>/dev/null
cat vault/projects/<name>/whats-real.md 2>/dev/null
```

Copy the template to `vault/projects/<name>/whats-real.md`, set the milestone and its date in the
frontmatter, and link the project root in the body by full path (only after checking it exists). Ask, one
question at a time: "what should work at this milestone?", then go item by item.

### 2. Classify each item (you)

For each item ask: "how do you know?". If the answer is a command, run it now. If it runs and the output
supports the claim, it goes to `Works` with the proof. If it looks like it works but is faked (a
fixture, a canned answer, a manual step), it goes to `Simulated or demo`, with what is faked. Otherwise
`Unknown`, with what would settle it.

### 3. The diary (you)

Append to `vault/projects/<name>/diary.md` (create it with the dated entry if it does not exist, with
a link to the project root): one dated entry of a few lines. Never rewrite an earlier entry.

### 4. Check, after the milestone (you)

Re-run every proof in `Works`. For each: same output, keep it and update the date; different output or
failure, move it to `Unknown` with the date and what happened. Review `Simulated or demo` and `Unknown`:
anything that became real moves up only through step 2. Add a diary entry with the counts.

### 5. Run the gate

```bash
python3 core/gate.py
python3 core/ring.py --vault vault --gate
```

## The output

`vault/projects/<name>/whats-real.md` (modelled on the template) and `vault/projects/<name>/diary.md`.

## Never

- Put an item in `Works` without a proof you ran in this session.
- Keep an item in `Works` after its proof failed on re-run.
- Delete an item to make the page look better.
- Rewrite an old diary entry.
