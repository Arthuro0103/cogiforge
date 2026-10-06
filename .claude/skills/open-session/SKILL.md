---
name: open-session
description: Opens a work session on one workbench project. Takes a project NAME, reads its root (vault/projects/<name>/instructions.md), the latest diary entries and its open tasks, and returns in a few lines where the project stands and what the last session left behind. Reports only what is in the files; when the file's status disagrees with what the disk shows, it becomes a question, never a verdict. TRIGGERS - "abrir sessão do <projeto>", "/open-session <project>", "onde parei no <projeto>", "resume <project>", "what is left on <project>". Do NOT trigger without a project name (ask which one, or list vault/projects/), nor to close the day (that is close-session), nor to get to know the user (that is onboard), nor for a loose code question.
---

# open-session: start by knowing where you stopped

## Why it exists

A new session does not remember the previous one. Without a starting point, the user spends the first ten
minutes rebuilding context from memory or, worse, redoes what was already done. The real state of the
project lives in files; someone has to read the right ones, in the right order, and hand it over **short**.

## The rules

1. **No project name, no run.** Ask which one (list the folders in `vault/projects/`). Never guess.
2. **Report only what you read.** Every line of the briefing points to the file it came from. If you did
   not read it, you do not claim it.
3. **Disagreement becomes a question.** If the file's `status:` disagrees with the disk (for example,
   marked `paused` with a commit from yesterday), show both sides and ask. Status is the user's decision, not mine.
4. **Short briefing.** Ceiling of 12 lines in the chat. Whoever needs the whole file opens it.
5. **Read-only.** This skill writes nothing in `vault/`.
6. **Stop at the generated block.** If the root has a block between the markers `<!-- hub:start` and
   `<!-- hub:end`, it is only a list of links: do not read below it.

> Talk to the user and write prose (notes, briefings, profile lines) in the language the user writes in. Never translate a quote: verbatim quotes stay in the original language. Fixed tokens (frontmatter keys, status values, paths, enums) stay exactly as written.

## The steps

### 1. Find the project (you, Claude)

```bash
ls vault/projects/
test -f vault/projects/<name>/instructions.md && echo ok
```

Without the root, say so and stop: *"vault/projects/<name>/instructions.md does not exist"*. If the name
matches more than one folder, ask which.

### 2. Read the root (you)

Open `vault/projects/<name>/instructions.md` up to the hub marker. From the frontmatter note: `type`, `status`,
`declared_target`. The `declared_target` is what the user said they want; the rest is context.

### 3. Read the diary (you)

```bash
ls -t vault/memory/diary/*.md 2>/dev/null | head -3
```

Open the three most recent and look only for what talks about the project (`grep -i "<name>"` helps). If a
recent briefing also exists (`ls -t vault/memory/briefings/ | head`), check the newest one that mentions the project.
If the folder is empty, this is the first session: say so.

### 4. Count the open tasks (one command)

```bash
for f in vault/tasks/*.md; do
  grep -q "projects/<name>/instructions" "$f" 2>/dev/null && grep -q -E "^status: *(open|in-progress)" "$f" 2>/dev/null && echo "$f"
done
```

List at most 5, `in-progress` first, then `priority: high`, showing the `title:` of each. If there
are more than 5, say how many were left out.

### 5. Check against the disk (you)

```bash
git log --oneline -5 -- vault/projects/<name> 2>/dev/null   # empty = no commits yet
git status --short vault/projects/<name>
```

Compare with what the root claims (status, dates). Any disagreement goes into the briefing as a question.

### 6. Deliver (you)

```
Project: <name>   status: <from the file>   target: <declared_target, one line>
Where it stopped:  <1-2 lines from the latest diary entry, with the date>
Still open:        <up to 5 tasks, title and status>
Attention:         <disagreement from step 5, as a question; omit if none>
Possible next step: <one suggestion, marked as my suggestion>
```

End by asking where the user wants to start.

## Never

- Run without a project name, or pick the project on your own.
- Change `status:` or any other field of the root.
- Invent "where it stopped" when the diary is empty.
- Dump the whole file into the chat.
