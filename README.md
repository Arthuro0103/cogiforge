<p align="center">
  <img src="assets/banner-v2.svg" alt="cogiforge: a second brain that learns how you work. Obsidian and Claude Code. It writes nothing about you that you did not say." width="100%">
</p>

**cogiforge is a second brain on Obsidian + Claude Code that learns how you work, and writes nothing about you that you did not say.** *Cogito, ergo sum*: a creative workbench for your head. It holds your work, your school and your personal life in one place, **organizes your projects, ideas and tasks, helps you write and plan, and gets better with you** as you use it.

> **Status: alpha (v0.x).** Built from the author's own working vault and used, so far, only by the
> author. Skills, docs and the vault template are in English. If you want to use it in Portuguese, see
> docs/TRANSLATING.md (glossary and a checklist). Step by step for each part: [TUTORIAL.md](TUTORIAL.md).

## Why it exists

cogiforge came out of using Claude on a real vault. Three decisions shaped it:

1. **Claude does not decide who you are.** Nothing about you is written unless you said it. A line only enters your profile with your "yes", the date and your literal quote.
2. **A rule stays only if a real failure justifies it.** Every rule in this repo comes from a dated mistake, and has a test that goes red without it. Examples from [WHY.md](WHY.md): a link checker that reported OK while 58 links were broken, a check that touched nothing and still said OK, a gate that was bypassed with `--no-verify` three times and then six.
3. **It proposes, you decide.** The skills write suggestions to files. Nothing changes behind your back.

![The author's own vault as a graph: every dot is a note, every line a link. File names are removed.](assets/vault-graph.png)

*The author's own vault, drawn as a graph. Every dot is a note and every line is a link between two notes. File names are removed.*

## What you get

| Piece | What it does |
|---|---|
| `vault/` | The workbench: `inbox/` for quick capture, `notes/` for processed notes, `projects/` with one root file per project, `memory/` for what *you* told it, `tasks/` for tasks. Open this folder in Obsidian. |
| `/onboard` | Onboarding. Asks one question at a time, each following your last answer, and writes what **you said**, dated and quoted. It never guesses. |
| `/open-session <project>` | Starts work on a project: reads its root file, the last diary entries and the open tasks, and tells you where you stopped. |
| `/close-session` | Ends the day: diary, a briefing per session, the **pains you voiced** collected in one file, tasks opened for what is pending. It commits only if you say so and never pushes. |
| `/task-observer` | Watches how you work and **only proposes** improvements (a missing skill, a step you repeated three times, a correction you made twice). You decide. |
| `/claude-corner` | When you say you are leaving, Claude uses that time to reread your notes, find real connections and test ideas in a throwaway place. It **only proposes**, in a file. |
| Tasks (**TaskNotes**) | Tasks are notes in `vault/tasks/`, managed by the public [TaskNotes](https://github.com/callumalpass/tasknotes) Obsidian plugin (MIT). Not bundled: you install it from Obsidian's community plugin store. `open-session` and `close-session` read and write the same format. |
| Connection map (**graphify**, optional) | The public [graphify](https://github.com/Graphify-Labs/graphify) (Apache-2.0) maps your notes into a graph you can query. Install it yourself; its output folder is git-ignored. See the tutorial. |
| `/adapt-skill` | Helps you write **your own** skill from a worksheet in `vault/skill-worksheets/`. One question at a time; Claude never writes it for you, and "this is not for me" is a valid answer that gets recorded. |

## How it improves with you

Three loops, and in all of them the decision stays with you:

1. **Pains.** At the end of a session your own words about what hurt are saved, dated, in `vault/memory/ideas/_pains.md`.
2. **Proposals.** `task-observer` and `claude-corner` write suggestions to files. Nothing is changed behind your back.
3. **Your own skills.** The worksheets teach how a skill is built, and `adapt-skill` walks you through making yours. You are not handed a finished one.

![How cogiforge improves with you: your pains, its proposals, your decision, your own skills](assets/flow.svg)

One hard rule runs through everything: **Claude does not write anything about you that you did not say.**
It proposes; a line only enters your profile with your "yes", with the date and your literal quote.

## Quickstart

You need `git`, Python 3.10+, Obsidian and Claude Code. macOS and Linux; Windows is untested. To run this
repo's own tests you also need `pytest` (`python3 -m pip install pytest`); nothing else in the repo uses it.

```sh
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
sh install.sh      # turns the pre-commit hook on and proves it works
claude              # run Claude Code at the repo root
```

Then, inside Claude Code, type `/onboard`. Open `vault/` as a vault in Obsidian. When you have a
project, `/open-session <name>` to start and `/close-session` to end the day. The example project
`vault/projects/example-my-first-project/` shows the shape. Tasks need the public TaskNotes plugin
(install it from Obsidian's community plugins), and the optional connection map needs graphify: both are
in the [tutorial](TUTORIAL.md).

## Teams and schools

One vault for a group, one folder per person: `vault/people/<handle>/` (memory, inbox, diary). Turn it on with
`sh install.sh --team <your-handle>`: it writes `vault/roles.txt` with you as admin (your `git config user.email`)
and copies `vault/people/_template/`. Add people as lines `handle  admin|member  email`. Without `roles.txt`
nothing changes: solo mode is identical.

- **admin** passes everything. **member** works in their own folder, in `notes/`, and in existing projects; the pre-commit hook blocks a member who touches another person's folder, `roles.txt`, `areas.txt`, or creates a project, and blocks an author who is not in `roles.txt`.
- **The honest limit:** git has no permission per folder. The roles are a convention plus a local hook, and `git commit --no-verify` skips it. Real enforcement is the host: add a `CODEOWNERS` file (for example `vault/roles.txt @your-org/admins` and `vault/people/ana/ @ana`) and turn on branch protection with required reviews.
- **Everyone who clones reads everything.** What is intimate goes in `vault/people/<handle>/private/`, which is gitignored and never leaves your machine.
- `install.sh --team` lists `vault/roles.txt` in `.leakignore`, because the e-mails there are deliberate.

## What keeps it healthy

This is the foundation under the workbench. It is deliberately small and runs on Python's standard library only.

- **Orphan gate.** The pre-commit hook blocks a note that links to nothing and nothing links to. `inbox/` is exempt: if quick capture gets blocked, people uninstall the thing. Only notes in *that* commit are blocked; others just get a warning.
- **Link check** (`core/gate.py`). Dead links, broken links, a path that only matches by file name, a bad `area:`, unreadable files (reported as "could not read", never as OK).
- **Leak scanner** (`core/leak.py`). Blocks machine paths, e-mails, phone numbers, CPF and a **private list of terms that lives outside the repo**. Without that list it says `NOT_VERIFIED`, never "clean".
- **No Portuguese by accident** (`tests/test_no_portuguese.py`). The repo moved to English in October 2026, and this test fails on accented letters, common Portuguese words and the old Portuguese folder and script names. The few deliberate exceptions are in `tests/pt_allowlist.txt`, one `path: reason` per line, and a second test fails when an exception no longer exists or no longer needs to be one.
- **CI** (`.github/workflows/prova.yml`). Installs from a clean clone, runs the tests and the mutation check, and tries the orphan gate end to end. The step that proves the hook test goes red now insists on that exact failure: a renamed test once made it print "ok" without testing anything.

The hook can be bypassed on purpose with `git commit --no-verify`. Every rule here comes from a real,
dated failure, and each one has a test that fails without it: see [WHY.md](WHY.md).

## What is verified, and what is not

Measured on 2026-10-06, after the move to English, on one machine (macOS), in a fresh clone:

- Tests: after `sh install.sh` and `python3 -m pip install pytest`, `python3 -m pytest -q` gave **233 passed, 2 skipped**. Run before `sh install.sh`, one test fails on purpose: it checks that the hook is active.
- Mutation: `python3 tests/mutate.py` breaks every check one at a time and gave **160 of 160 mutants killed, 0 alive**. `python3 tests/mutate.py --dry` only checks, in seconds, that every mutant still applies (160 do, 0 inapplicable), so a rename that breaks one is caught before the long run.
- CI: the run for the English version ([run 37525945635](https://github.com/Arthuro0103/cogiforge/actions/runs/37525945635), 2026-10-06, commit `863cd21`) had **8 of 8 jobs green**, on ubuntu and macOS with Python 3.10, 3.11, 3.12 and 3.13. Each job starts from a clean checkout, runs `install.sh`, the tests, the mutation check and the leak scan, and proves the orphan gate end to end.
- Two tests compare this link checker with the author's private vault, which is not in this repo. They are **skipped** (reported as skipped, not as passed).
- **Nobody other than the author has used it yet.** If you are the first, tell us where you got stuck: that is the most useful thing you can send.

## Roadmap

`artigo`, `conselho`, `product-idea` and `consult-notes` as real skills (their worksheets are in `vault/skill-worksheets/` today); a skill that turns one of your own failures into a rule plus a test.

## License

MIT. See [LICENSE](LICENSE).
