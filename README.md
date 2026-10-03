# cogiforge

*cogi ergo sum*: a creative workbench for your head. A second brain on **Obsidian + Claude Code** that
holds your work, your school and your personal life in one place, **organizes your projects, ideas
and tasks, helps you write and plan, and gets better with you** as you use it.

> **Status: alpha (v0.x).** Built from the author's own working vault and used, so far, only by the
> author. Skills and notes are in **Portuguese** for now; this page is the English front door.
> Português completo: [LEIA-ME.md](LEIA-ME.md).

## What you get

| Piece | What it does |
|---|---|
| `vault/` | The workbench: `inbox/` for quick capture, `notas/` for processed notes, `projetos/` with one root file per project, `memoria/` for what *you* told it, `tarefas/` for tasks. Open this folder in Obsidian. |
| `/conhecer` | Onboarding. Asks one question at a time, each following your last answer, and writes what **you said**, dated and quoted. It never guesses. |
| `/abrir-sessao <project>` | Starts work on a project: reads its root file, the last diary entries and the open tasks, and tells you where you stopped. |
| `/fechar-sessao` | Ends the day: diary, a briefing per session, the **pains you voiced** collected in one file, tasks opened for what is pending. It commits only if you say so and never pushes. |
| `/task-observer` | Watches how you work and **only proposes** improvements (a missing skill, a step you repeated three times, a correction you made twice). You decide. |
| `/claude-corner` | When you say you are leaving, Claude uses that time to reread your notes, find real connections and test ideas in a throwaway place. It **only proposes**, in a file. |
| `/adaptar-skill` | Helps you write **your own** skill from a worksheet in `vault/fichas-de-skills/`. One question at a time; Claude never writes it for you, and "this is not for me" is a valid answer that gets recorded. |

## How it improves with you

Three loops, and in all of them the decision stays with you:

1. **Pains.** At the end of a session your own words about what hurt are saved, dated, in `vault/memoria/ideias/_dores.md`.
2. **Proposals.** `task-observer` and `claude-corner` write suggestions to files. Nothing is changed behind your back.
3. **Your own skills.** The worksheets teach how a skill is built, and `adaptar-skill` walks you through making yours. You are not handed a finished one.

One hard rule runs through everything: **Claude does not write anything about you that you did not say.**
It proposes; a line only enters your profile with your "yes", with the date and your literal quote.

## Quickstart

You need `git`, Python 3.10+, Obsidian and Claude Code. macOS and Linux; Windows is untested.

```sh
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
sh instalar.sh      # turns the pre-commit hook on and proves it works
claude              # run Claude Code at the repo root
```

Then, inside Claude Code, type `/conhecer`. Open `vault/` as a vault in Obsidian. When you have a
project, `/abrir-sessao <name>` to start and `/fechar-sessao` to end the day. The example project
`vault/projetos/exemplo-meu-primeiro-projeto/` shows the shape.

## What keeps it healthy

This is the foundation under the workbench. It is deliberately small and runs on Python's standard library only.

- **Orphan gate.** The pre-commit hook blocks a note that links to nothing and nothing links to. `inbox/` is exempt: if quick capture gets blocked, people uninstall the thing. Only notes in *that* commit are blocked; others just get a warning.
- **Link check** (`nucleo/portao.py`). Dead links, broken links, a path that only matches by file name, a bad `area:`, unreadable files (reported as "could not read", never as OK).
- **Leak scanner** (`nucleo/vazamento.py`). Blocks machine paths, e-mails, phone numbers, CPF and a **private list of terms that lives outside the repo**. Without that list it says `NAO_VERIFICADO`, never "clean".
- **CI** (`.github/workflows/prova.yml`). Installs from a clean clone, runs the tests and the mutation check, and tries the orphan gate end to end.

The hook can be bypassed on purpose with `git commit --no-verify`. Every rule here comes from a real,
dated failure, and each one has a test that fails without it: see [POR-QUE.md](POR-QUE.md) (in Portuguese).

## What is verified, and what is not

- `Tests: `python3 -m pytest -q` gave **186 passed, 2 skipped** on 03/10.`
- `Mutation: `python3 tests/mutar.py` breaks every check one at a time and gave **102 of 102 mutants killed, 0 alive** on 03/10.`
- `CI: the workflow is in the repo and its first run on this repo is still pending. Until it is green, "works on a clean clone" was checked by hand only (clone, `sh instalar.sh`, an orphan note blocked at commit) on macOS.`
- Two tests compare this portão with the author's private vault, which is not in this repo. They are **skipped** (reported as skipped, not as passed).
- **Nobody other than the author has used it yet.** If you are the first, tell us where you got stuck: that is the most useful thing you can send.

## Roadmap

`artigo`, `conselho`, `ideia-de-produto` and `consultar-notas` as real skills (their worksheets are in `vault/fichas-de-skills/` today); a command to list tasks; a skill that turns one of your own failures into a rule plus a test.

## License

MIT. See [LICENSE](LICENSE).
