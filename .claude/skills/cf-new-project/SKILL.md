---
name: cf-new-project
description: Creates a new project in the user's workbench without hand-copying the example. Asks one question at a time (the name in a few words, then "what exists in the world when this project succeeds?", then type and status with defaults), copies the user's sentence word for word into declared_target, shows a --dry-run, waits for an explicit "yes", then runs tools/new_project.py, which writes the project root, adds the row to projects/_index.md, runs hub.py, and then gate and ring are run and their rc reported. TRIGGERS - "/cf-new-project <name>", "new project", "create a project", "start a project called X", "add a project". Do NOT trigger for a project that already exists (that is cf-open-session), to bring in an existing base or vault (that is cf-import-knowledge or cf-adopt), to adopt an existing vault (that is cf-adopt), nor to decide whether an idea is worth doing (that is cf-brainstorm).
---

# cf-new-project: a project that is registered from the first minute

## Why it exists

Creating a project by hand means copying a folder, editing the frontmatter, adding a row to the index and
running the hub. Forget the row and `hub.py` prints `OK <name>` and then `NOT IN INDEX`. This skill asks
the few things only the user knows, and `tools/new_project.py` does the rest and checks it. No API, no network.

## The rules

1. **One question per message.** The next depends on the answer. A short answer is a valid answer.
2. **The target is the user's sentence, word for word.** Copy it into `--target` unchanged: no fixing, no
   shortening, no translating. Never invent it, never suggest one to fill a blank. If they have none yet, say
   so and stop: the project is not created without it.
3. **Never write about the user what they did not say** (rule 2 of the repo). The tool writes only the name,
   the target, the type and the status. Do not add a "why this matters" or any other text for them.
4. **Never create without the "yes".** First `--dry-run`, show it, and wait. Anything other than a clear
   "yes" (or "sim") means nothing is created.
5. **Never touch an existing project.** If the name is taken, ask for another.
6. **Report the real rc.** If a check fails, show its message; do not say the project is fine.

> Talk to the user in the language the user writes in. Never translate their sentence.

## The steps

### 1. The name (ask)

Ask: "What do you call this project, in a few words?" Then **you** propose a slug (lowercase letters,
numbers, hyphens, at most 40 characters, for example `my-first-app`) and ask them to confirm or change it.
**STOP and wait.**

### 2. The target (ask)

Ask exactly: "What exists in the world when this project works out?" One sentence is enough. **STOP and wait.**
Their answer, word for word, is `--target`.

### 3. Type and status (ask)

Ask once, with the defaults visible: "Type? (default `software`; free: school, work, personal, writing...)
Status? (default `active`; or `paused`, `closed`)". Silence or "default" means the defaults.
Optionally a short "what it is" for the index; if they give none, the tool reuses the target. **STOP and wait.**

### 4. Show what would be created (command)

```bash
python3 tools/new_project.py <name> --target "<their sentence>" --type <type> --status <status> --dry-run
```

Show the output as it is and ask: "Create it? (yes/no)". **STOP and wait.** Rule 4 applies.

### 5. Create (command, only after the "yes")

Run the same command without `--dry-run`. It writes `vault/projects/<name>/instructions.md`, adds the row
to `vault/projects/_index.md`, runs `tools/hub.py` and checks it.

### 6. Check and report (command)

```bash
python3 core/gate.py
python3 core/ring.py --vault vault --gate
```

Deliver: where the project is, the rc of `gate` and of `ring`. If either is not 0, show the message and say
what it names. Then say the next step is theirs: open `projects/<name>/instructions.md` and write in their
own words why it matters (or run `/cf-open-session <name>`).

## Never

- Create, or run the tool without `--dry-run`, before the user says "yes".
- Invent, complete, fix or translate the target.
- Fill the other sections of `instructions.md` for the user.
- Say "done" without having run `gate` and `ring` and read their rc.
- Edit `vault/projects/_index.md` by hand: the tool does it.
