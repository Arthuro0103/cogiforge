# Tutorial: using each part of the workbench

This guide goes from zero to your first day of use, one part at a time. For each part: **what to do**
and **what you should see**. If what appears on your screen is different, it is a defect in the guide or
in the repo: tell us.

## What was checked, and what was not

| Part | How it was checked |
|---|---|
| `install.sh`, hook, gate, ring, leak, hub | **Run in a fresh clone on Oct 6, 2026**, after the move to English, and the output blocks below are the real ones (your own home folder shows as `~`). |
| `open-session`, `close-session` | **Run in a real Claude Code session on Oct 3**, before the commands were renamed and translated. Since the rename they have not been run in a live session yet. The replies below are examples. |
| `onboard`, `adapt-skill` | Run up to the **first question** on Oct 3 (they are conversations; the rest depends on you), also before the rename. |
| `task-observer`, `claude-corner` | **Not exercised yet.** What is written here comes from the skill itself. |
| TaskNotes (plugin) and graphify | They follow the projects' own documentation. `graphifyy` was installed in an isolated environment and `graphify --help` was checked; **the plugin inside Obsidian and `/graphify` on a vault were not run.** |

All skills were tested on the author's machine, which has its own Claude Code settings. That does not
prove they work the same way on yours. This is why the guide asks you to write down where you got stuck.

## 0. Before you start

You need `git`, Python 3.10 or newer, [Obsidian](https://obsidian.md) and Claude Code. Only to run the
repo's own tests (section 14) you also need `pytest`: `python3 -m pip install pytest`.
It works on macOS and Linux; Windows was not tested. Clone with `git clone` (do not download the zip: the
hook depends on git).

```sh
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
```

## 1. Install the hook

**Do:**

```sh
sh install.sh
```

**You see** (real output):

```
OK — hook active (core.hooksPath=.githooks) and the ring selftest passed.
Test it yourself: create a note without a link in vault/notes/ and run git commit.
```

What this did: it turned on git's `core.hooksPath` in this clone and proved that the orphan gate fails
what it should fail. **Without this step the hook exists but does not protect you**, because that git
setting is local and the clone does not bring it. If you see `ERROR` and `Installation was NOT
completed`, read the line above it: it says what was missing (git, Python 3.10, or being inside a clone).

## 2. Open the vault in Obsidian

In Obsidian: *Open folder as vault*, and choose the **`vault/`** folder of the repo, not the root. You run
Claude Code at the **root** of the repo, and it reads and writes only inside `vault/`.

## 3. Install TaskNotes (the tasks)

[TaskNotes](https://github.com/callumalpass/tasknotes) is a public Obsidian plugin (MIT license,
maintained by a person outside this project). Each task becomes a note, with a calendar and time
tracking. **It does not come with the repo**: you install it from Obsidian's store.

**Do:**

1. Obsidian → *Settings* → *Community plugins* → turn community plugins on.
2. *Browse* → search for **TaskNotes** → *Install* → *Enable*.
3. *Settings* → *TaskNotes* → general tab: set **Default tasks folder** = `tasks`, and leave
   **Identify tasks by** on **Tag** with the tag `task`.

**You should see** (from the plugin's documentation; **not checked here inside Obsidian**): the example
task `vault/tasks/write-the-first-example-note.md` showing up in the plugin's views, and each task created
through the interface becoming a `.md` file in `vault/tasks/`.

> The option names above are the ones in the plugin's documentation for version 4.13.8. If they differ in
> yours, what matters is: **tasks folder = `tasks`** and **task identified by the tag `task`**.

The format of a task (the plugin and the skills write the same one):

```yaml
---
tags:
  - task
title: Call the dentist
status: in-progress        # open | in-progress | done
priority: high             # none | low | normal | high
projects:
  - "[[projects/example-my-first-project/instructions|example]]"
---

Done when: appointment booked.
```

Two house rules about tasks: `tasks/` is **not** failed as an orphan note (the plugin creates a task
without asking for a link, and failing there would make you uninstall it), and the gate **does not judge
the YAML** there (the plugin adds its own fields, such as tracked time). A dead link inside a task still
fails.

> There are also public command-line tools from the same author (`npm install -g tasknotes-cli` and
> `npm install -g mdbase-tasknotes`, both MIT). They are not needed here and were not tested.

## 4. Your first day: `/onboard`

**Do:** with Claude Code at the repo root (`claude`), type `/onboard`.

**You see** (example, in any language; a real reply in a clone where the profile was empty):

```
Let's start. Your profile is empty, so this is the first time.

I ask this so the workbench serves what weighs on you for real, and not a generic template.

Which of these areas weighs on you most today?
1. Work   2. School or study   3. Personal life   4. A specific project
You can pick one, combine several, or answer in your own words. "I prefer not to say" is also fine.
```

One question at a time, each following your answer. What comes out of it:
`vault/_questions_about_me.md` filled in and **proposed** lines for `vault/memory/profile.md`, with the
date and your verbatim quote. Nothing enters the profile without your "yes", and Claude does not infer
what you did not say. A short answer is fine, and so is "I prefer not to say".

## 5. Create your first project

A project is a folder in `vault/projects/` with an `instructions.md` file (the **root**). Everything that
comes out of the project links back to it.

**Do:**

```sh
cp -R vault/projects/example-my-first-project vault/projects/my-app
```

1. Open `vault/projects/my-app/instructions.md` and change `type`, `status` (for example `active`,
   `paused` or `closed`) and `declared_target` (one sentence: what exists in the world when the project
   works out).
2. In `vault/projects/_index.md`, add a line **inside the table** (right below its last row, not after
   the paragraph that follows it):
   `| [[projects/my-app/instructions\|my-app]] | active | software | My first app. |`
3. Run the hub, which writes into the project root the list of all its files:

```sh
python3 tools/hub.py
python3 tools/hub.py --check
```

**You see** (real output):

```
OK         example-my-first-project
OK         my-app
```

If you forget step 2, `--check` answers `NOT IN INDEX my-app (every project goes in
projects/_index.md)` and exits with an error. A project root that nobody points to also shows up as an
orphan in the ring (step 6).

## 6. Write a note, and the hook at work

A note is a `.md` file in `vault/notes/<area>/`. The valid areas are in `vault/areas.txt` (the folder has
the same name as the note's `area:`). The minimal template is in `vault/CLAUDE.md`.

**a) A loose note is blocked.** Create `vault/notes/learning/loose.md` with a heading and text, but with
no link at all, and try to commit:

```sh
git add vault/notes/learning/loose.md
git commit -m "loose note"
```

**You see** (real output):

```
  ⛔ COMMIT BLOCKED — a note in this commit has no edge in the graph

     FAILS — 1 note(s) with no inbound or outbound link:
        notes/learning/loose.md
     
     How to fix: open the note and connect it to a note that EXISTS with a [[wikilink]] in the middle of the text
     (where the connection is real; a block of links in the footer is not the way), or point to it from an
     existing note.
     A link to a file that does not exist does not count. Just a quick capture? Drop it in inbox/ (or create the task in tasks/): they are exempt.
     Deliberate bypass: git commit --no-verify
     
  NOT_VERIFIED: private blocklist missing — only the generic patterns ran. Create ~/.config/cogiforge/blocklist.txt (one term per line) to check the private part.
  Deliberate bypass: git commit --no-verify
```

**b) Link the note in the middle of the text and the commit passes.** Add to the body, for example:
`... [[projects/example-my-first-project/instructions|the example project]] gets this note.` The link is a
**full path from `vault/`**, and it counts where the connection is real.

**c) Quick capture is never blocked.** A file in `vault/inbox/` goes in without a link. This is on
purpose: someone who gets blocked while jotting down an idea uninstalls the tool.

**d) Personal data is blocked.** A file that mentions a machine path (`/Users/<name>/...`), an e-mail, a
phone number or a CPF (Brazilian tax ID):

```
  ⛔ COMMIT BLOCKED — personal data leak in what is going into the commit

     vault/inbox/leaked.md:1: path
     1 finding(s) in 1 file(s), of 1 scanned
     NOT_VERIFIED: private blocklist missing — only the generic patterns ran. Create ~/.config/cogiforge/blocklist.txt (one term per line) to check the private part.

  Take the data out of the file (the output above says file:line:type, never the data).
  Deliberate bypass: git commit --no-verify
```


The output says **where** and **what type**, never the data that was found.

**e) Your private blocklist.** Besides the patterns above, the scanner checks a list of your own terms
(names, companies, projects that must not appear). It lives **outside the repo**, in
`~/.config/cogiforge/blocklist.txt`, one term per line. Without it, the hook does not block, but it warns:

```
  NOT_VERIFIED: private blocklist missing — only the generic patterns ran. Create
  ~/.config/cogiforge/blocklist.txt (one term per line) to check the private part.
```


This means "the private part was **not checked**", and never "it is clean".

**f) Check by hand at any time:**

```sh
python3 core/gate.py        # links, areas and headers
python3 core/ring.py        # lists the orphan notes
python3 core/leak.py .      # looks for personal data
```

The gate answers `N note(s), 0 fail, 0 COULD NOT READ` when everything is fine. It only checks what is
**inside** `vault/`: a file from outside exits with an error (code 2), never as "ok".

## 7. `/open-session`: where you left off

**Do:** say `open session for example-my-first-project` (or the name of your project), or use
`/open-session <project>`. We tested it with the sentence. Without a project name it does not trigger.

**You see** (example, in any language; an abridged real reply in the clean clone, with the in-progress task
created in step 3):

```
Project: example-my-first-project · status: active · target: still the template text (...)

Where you left off: nowhere. vault/memory/diary/ and vault/memory/briefings/ have no files,
so this is the first session.

Left open (2 tasks):
- in-progress, high priority: Call the dentist
- open: Write the first note linked to the example project

Attention: The dentist task points to this project. Is that on purpose or is the link wrong?

Possible next step (my suggestion): do the open task of writing the first note linked...
Where do you want to start?
```

It **only reports what is in the files**, and where the disk disagrees with what a file claims it **asks**,
it does not decide. The suggestion comes marked as a suggestion.

## 8. `/close-session`: closing the day

**Do:** when you finish, `/close-session`. If something hurt, say it in your own words.

**You see** (example, in any language; abridged; we said "every time I create a new project I forget to add
it to the index" and asked for a task):

```
Files created (everything in vault/):
- tasks/new-project-goes-in-the-index.md, open, on the project my-app.
- memory/briefings/2026-10-03-project-my-app.md
- memory/diary/2026-10-03.md
- memory/ideas/_pains.md (1 line added)

Verifiers: gate.py: 27 notes, 0 fail. ring.py --gate: no orphans.

Finding: the my-app line in projects/_index.md landed after the "Possible statuses" paragraph, outside
the table. (...) Do you want me to move the line into the table? After that, do you want me to commit?
```

What it does: the day's **diary**, one **briefing** per session (with a full-path link to the project root
in the body, no `## Connections` block), the **pains** collected only from **your** words in
`vault/memory/ideas/_pains.md` (`date | verbatim quote | source`; without a verbatim quote the line does
not go in), **tasks** opened in the TaskNotes format, and it runs the gate and the ring. **It commits only
if you tell it to and never pushes.** What it created passed the hook when committed, with no adjustments.

## 9. `/task-observer`: the workbench learns from you

**Do:** during the work, ask for `/task-observer`, or say "observe this session".

**What it does** (described in the skill; **not exercised yet**): it looks for three signals: a skill that
was missing, a step repeated three times, a correction you made twice. It adds one line per proposal to
`vault/memory/observations.md` (date, what it saw, what it proposes). **It only proposes.** It never
writes to `profile.md`, `patterns.md`, `decisions.md` or to `vault/notes/`, and **it never creates a
skill**: the agenda is yours, and what guides skill creation is `/adapt-skill`.

## 10. `/claude-corner`: the time you are away

**Do:** before leaving, say "I'm leaving for an hour".

**What it does** (described in the skill; **not exercised yet**): if you asked for something before
leaving, that request is done **in full first**. Then, for the time you say (at most 1h30), Claude rereads
your notes, looks for real connections, reads the pains and the projects, and tests ideas in a throwaway
place **outside `vault/`**. It **only proposes**, in `vault/memory/corner/YYYY-MM-DD-<subject>.md`: it does
not assert, does not merge, does not push, does not install anything outside the throwaway place and does
not message anyone. When you return you get a short summary and the path of the file.

## 11. `/adapt-skill` and the worksheets: make your own skill

The skills `artigo`, `conselho`, `product-idea` and `consult-notes` **do not come ready-made**: they come
as **worksheets** in `vault/skill-worksheets/`, which explain the method from the inside. The idea is that
you decide whether you want a version of your own and write it, instead of receiving a finished one that
may not fit.

**Do:** `/adapt-skill`.

**You see** (example, in any language; abridged):

```
Did any skill in the catalog catch your attention? A skill is a script Claude follows when you call it.
I ask this to choose which worksheet we read together.

| skill | what it does |
| conselho | puts a costly decision through several angles that disagree and closes on a verdict |
| artigo | takes a thesis to text with no invented citation |
| product-idea | finds a real pain in what you already wrote and returns an idea |
| consult-notes | answers only with what your notes say, citing each note |

(...) I did not read the worksheets, so I do not claim which one would fit best.
You can pick one, ask for a suggestion from me, or say "none fits today". (...) Which one?
```

The path: **read the worksheet together → separate the method from what is only the author's → decide
whether it solves a pain of yours → write it with your answers → test it on a real case → record the
verdict** in `vault/memory/skills-reviewed.md`. Claude **never writes the skill for you**, and **"it is not
for me" is a valid answer** that gets recorded, with the reason. Without a pain of yours quoted, the
answer is "not now".

Before that, read `vault/skill-worksheets/anatomy-of-a-skill.md` (the seven parts of a skill and what
each one is for, in about 5 minutes).

## 12. Connection map with graphify (optional)

[graphify](https://github.com/Graphify-Labs/graphify) is a public project (Apache-2.0 license) that turns
a folder into a **network of concepts** you can query, instead of rereading the files. Here it helps
find what your notes have in common.

**Do** (once, in the terminal):

```sh
uv tool install graphifyy     # or: pipx install graphifyy
graphify install              # registers the skill in your Claude Code
```

The package name has **two `y`**: `graphifyy`. That is what the official repository (Graphify-Labs/graphify)
indicates; always check the address before installing a third-party package. `graphify install` writes the
skill in the configuration folder **of your user** (it applies to all your projects); with
`graphify install --project` it goes to `.claude/skills/graphify/` in this repo.

Then, in Claude Code, **at the repo root**:

```
/graphify vault
```

**You see:** a `graphify-out/` folder with `graph.html` (open it in the browser), `GRAPH_REPORT.md` (the
most connected concepts and the surprising connections) and `graph.json`. To query:
`/graphify query "<question>"`, `/graphify path "A" "B"` and `/graphify explain "concept"`.

- `graphify-out/` **is in `.gitignore`**: the map is generated from your notes and does not go to the repo.
- If `graphify-out/GRAPH_REPORT.md` exists, Claude reads it before looking for connections between notes.
- According to the project, **code** is read locally; the semantic reading of **notes and documents** goes
  through a model (your assistant, or a backend you configure). If your notes are sensitive, decide that
  before running it.
- **Not run here:** `/graphify` over a vault. We installed the package in an isolated environment and
  `graphify --help` listed the commands (`install`, `path`, `explain`, among others).

## 13. The hook blocked my commit

| What appears | What to do |
|---|---|
| `a note in this commit has no edge in the graph` | Connect the note to another one that **exists**, with `[[full/path\|text]]` in the middle of the text. Or drop the capture in `vault/inbox/`. |
| `personal data leak` + `file:line:type` | Remove the data from the file (the hook does not show the data, only the place). |
| `NOT IN INDEX <project>` (from `hub.py`) | Add the project as a row inside the table in `vault/projects/_index.md`. |
| `NOT_VERIFIED: private blocklist missing` | Not an error. Create `~/.config/cogiforge/blocklist.txt` if you want to check the private part. |
| `UNREADABLE` / exit code 3 from the gate | The file could not be read (permission, or not UTF-8 text). It does not mean "clean". |
| `ERROR: ... is outside vault` | The gate only checks what is inside `vault/`. Copy the file inside. |
| I want to commit anyway | `git commit --no-verify`. It is the deliberate bypass; use it knowing what you are skipping. |

## 14. Quick reference

| For | Command |
|---|---|
| turn the hook on and prove it works | `sh install.sh` |
| check links, areas and headers | `python3 core/gate.py` |
| list orphan notes | `python3 core/ring.py` |
| look for personal data | `python3 core/leak.py .` |
| rewrite the file list of each project | `python3 tools/hub.py` |
| check that the hub is up to date | `python3 tools/hub.py --check` |
| run the repo tests (needs `pytest`; run **after** `sh install.sh`, otherwise the hook test fails on purpose) | `python3 -m pytest -q` |
| break each check and require a red test | `python3 tests/mutate.py` |

| Skill | When |
|---|---|
| `/onboard` | the first time, and when you want to update the profile |
| `/open-session <project>` | when you start working on a project |
| `/close-session` | when you finish the day |
| `/task-observer` | during the work, so the workbench proposes improvements |
| `/claude-corner` | when you are about to leave |
| `/adapt-skill` | when you want a skill of your own from a worksheet |

Something did not match this guide? Write down the step, what you expected and what appeared, and send it.
