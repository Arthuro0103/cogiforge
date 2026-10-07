---
name: brainstorm
description: General brainstorming for any product, project, study, event or loose idea (pains are one possible input, not the only one). Asks about the goal one question at a time, scans what the vault already says (collection before internet) and declares the gap, proposes 3 genuinely different paths, compares them in a table by criteria the person picks (defaults - value, frequency of the problem, effort, dependence on others, reversibility), recommends one WITHOUT choosing for them, and closes in a brief at vault/projects/<name>/brief.md. HARD-GATE - no code, plan or project file before an explicit yes on the brief; answers are approve, revise or abort. TRIGGERS - "/brainstorm", "I have an idea", "help me think this through", "what could I build", "ideas for an event". Do NOT trigger when the path is chosen and the person wants it built, to pick between two existing options (that is a council), to mine pains for products (that is product-idea), nor to write the plan or code after approval.
---

# brainstorm: think before building, and stop at an approved brief

## Why it exists

The cheapest moment to change an idea is before anything exists. The usual failure is to jump from a
loose idea to a plan, and discover three weeks later that nobody needed it, or that a simpler path was
sitting next to it. This skill spends a few questions to put **three really different paths side by side**,
lets the person pick the criteria, and ends in one page they approved. It never builds.

Template: [[skill-worksheets/brainstorm-brief-template|brainstorm-brief-template]]. Copy it, do not edit it.

## HARD-GATE

**Until the person writes an explicit "yes" (or `approve`) on the brief, there is no code, no execution
plan and no project file.** The only thing written before that is the draft brief, and only after the
person agreed to see it. When the brief is approved, stop and say what the next step is; do not take it.

## The rules

1. **One question per message.** The next depends on the answer.
2. **Context before options.** One sentence saying why you ask, then 2 to 4 concrete options
   (`AskUserQuestion`), always with room for a free answer. A short answer is a valid answer.
3. **Skip what is already answered.** If the person arrives with the goal, the audience or a pasted
   document, do not ask again. Say which questions you skipped and why, in one line.
4. **Collection before internet.** Search the vault first. Say what you found, with its path, and name the gap.
5. **Three paths that really differ.** Different in approach, not in size or polish. If two look alike, replace one.
6. **Criteria are the person's.** Offer defaults, let them drop, add or reweigh.
7. **Recommend, never choose.** Say which one you would pick and why, then ask. The decision is theirs.
8. **Nothing about the person is deduced.** Only what they said goes into the brief.

> Talk to the user and write the brief in the language the user writes in. Fixed tokens (frontmatter keys,
> status values, paths) stay exactly as written.

## The steps

### 1. Understand the goal (you and the user)

Ask, one at a time, until you can write the goal in one sentence the person agrees with: what they want to
exist, for whom, and by when if there is a date. Cover: the goal, who it is for, what has been tried,
what is fixed (budget, time, tools). Skip any already known.

### 2. Scan the vault (you)

```bash
python3 tools/ask.py search "<query>" --top 8
ls vault/projects/ vault/notes/ 2>/dev/null
```

Use `ask` for retrieval if present, otherwise `grep -ril`. Report what exists on the subject and where, then
the **gap**: what the vault does not say. A gap is a result, not a failure. Do not go to the internet unless
the person asks.

### 3. Three paths (you)

Write exactly **3** paths, each in three lines: the idea, what it bets on, what would make it fail. Check
them against each other; if two share the same bet, swap one for a different bet.

### 4. Compare (you, criteria chosen by the user)

Ask which criteria matter, offering the defaults: **value**, **how often the problem happens**, **effort**,
**dependence on third parties**, **reversibility**. Then one table, paths in the columns, criteria in the
rows, a short phrase in each cell (not scores that pretend to be exact). Mark what you are guessing.

### 5. Recommend (you)

One path, with the reasons tied to the criteria the person chose and one line on the strongest case against
it. End with the question "which one do you want to take forward?". Do not continue until they answer.

### 6. Detail and write the brief (you)

Detail only the chosen path. Fill the template: who uses it, the problem, the journey, the empty, loading,
success and error states when it is a product, what is out of scope, observable criteria, and the
definition of done. Save to `vault/projects/<name>/brief.md` with `status: draft`, linking the project root
by full path (only after checking it exists). If the project does not exist yet, show the brief in the chat
and say the project folder comes after approval.

### 7. Approval

Ask: `approve`, `revise` or `abort`.

| answer | what you do |
|---|---|
| `approve` | set `status: approved`, run the gate and the ring, say the next step and **stop** |
| `revise` | ask what to change, one question at a time, rewrite, ask again |
| `abort` | leave the brief as `status: aborted` with the reason in one line, or delete the draft if the person asks |

```bash
python3 core/gate.py
python3 core/ring.py --vault vault --gate
```

## Never

- Write code, an execution plan or a project file before the explicit yes.
- Offer three paths that are the same path in different clothes.
- Pick the path for the person, or hide the case against your own recommendation.
- Ask what the person already told you.
- Go on after approval: the next step is named, not started.
