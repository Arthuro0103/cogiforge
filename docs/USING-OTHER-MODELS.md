# Using the vault with other models

cogiforge is plain Markdown plus a few Python scripts. Any coding agent can work in it if it reads the
rules. The rules are in [AGENTS.md](../AGENTS.md), written without any Claude-only feature.

> Claude Code, Codex, Cursor and Gemini CLI were checked on **2026-11-10** against each tool's own documentation; the "Others" row was last checked on 2026-10-07. Tools change quickly: trust the
> tool's docs over this table. What I could not confirm is marked `[VERIFY: ...]`.

## Which file does each agent read

| Agent | Reads `AGENTS.md`? | Source |
|---|---|---|
| OpenAI Codex | Yes: from the git root down to the working directory; closer files override; 32 KiB combined by default (`project_doc_max_bytes`). In each directory it tries `AGENTS.override.md`, then `AGENTS.md`, then the names in `project_doc_fallback_filenames`. Skills: it scans `.agents/skills`. `/import` brings AGENTS.md, skills and memories from Claude Code or Cursor | [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [skills](https://learn.chatgpt.com/docs/build-skills), [import](https://learn.chatgpt.com/docs/import) |
| GitHub Copilot | Yes: "the nearest `AGENTS.md` file in the directory tree will take precedence" | [GitHub docs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions) |
| Cursor | Yes: "Cursor supports AGENTS.md in the project root and subdirectories." Its own rules live in `.cursor/rules` as `.mdc` files | [Cursor rules](https://cursor.com/docs/context/rules); skills: [Cursor skills](https://cursor.com/docs/skills) |
| Gemini CLI | **Not by default.** It reads `GEMINI.md`; set `"context": { "fileName": ["AGENTS.md", "GEMINI.md"] }` in its `settings.json`. **Availability changed:** on 2026-06-18 it stopped serving free, Google AI Pro and Ultra individual users (moved to Antigravity CLI); it stays available for Standard and Enterprise and with paid API keys | [Gemini CLI docs](https://geminicli.com/docs/cli/gemini-md/); [Google announcement](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/); [repo README](https://github.com/google-gemini/gemini-cli) |
| Claude Code | Reads `CLAUDE.md` first; reads `AGENTS.md` when there is no `CLAUDE.md` above it, in v2.1.277 or newer. This repo has both, so it reads `CLAUDE.md`, which links to `AGENTS.md` | [Claude Code docs](https://code.claude.com/docs/en/memory) |
| Others (Windsurf, Zed, Aider, Devin, Jules, ...) | listed as supporting the format | [agents.md](https://agents.md); `[VERIFY: each tool's own page before relying on it, checked 2026-10-07]` |

The format itself is described on [agents.md](https://agents.md) as "a README for agents".

If your agent does not read `AGENTS.md`, the fallback always works: **start the session with "read
`AGENTS.md` at the repo root and follow it"**, or paste it into the tool's own instruction field.

## What you lose without Claude Code's skills

The skills in `.claude/skills/<name>/SKILL.md` are text. Another agent can read the file and follow the
steps (AGENTS.md lists them). What you lose is the machinery around the text:

| Claude Code gives you | Without it |
|---|---|
| Skills load by themselves when your request matches their description, and run as `/name` | Depends on the agent (see below); where they do not load, you name the skill yourself and ask the agent to read and follow it |
| Skills can start helper agents in parallel | Run one step at a time; slower, same result |
| The skills were written and tested against Claude's behavior | A weaker or different model may skip a step, or answer from memory instead of from the notes. Read what it did |
| Claude Code's own memory and hooks | The vault's hook (`sh install.sh`) is plain git: it works with any agent that commits |

Who loads `.claude/skills/<name>/SKILL.md` on its own, per each tool's own docs:

- **Claude Code** reads `.claude/skills`.
- **Cursor** loads `.claude/skills` "for compatibility", and also `.agents/skills` ([Cursor skills](https://cursor.com/docs/skills)).
- **Codex** scans `.agents/skills` and **not** `.claude/skills` ([Codex skills](https://learn.chatgpt.com/docs/build-skills)).

For Codex, from the repo root: `mkdir -p .agents && ln -s ../.claude/skills .agents/skills`. `install.sh`
does not do this on purpose: symlinks break on Windows and in zips, and Cursor may then see the skills
twice (`[VERIFY: untested]`). Or use Codex's `/import` ([Codex import](https://learn.chatgpt.com/docs/import)).
`[VERIFY: I read these docs; I did not run Codex or Cursor against this repo's skills]`

Claude Code with the Bash sandbox on: open it at the **repo root**, not inside `vault/`. The Claude Code
[CHANGELOG](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md), version 2.1.319, says:
"Changed nested skill loading: with the Bash sandbox on, skills in `.claude/skills` folders below the
starting folder load only if you start Claude Code there or `/cd` there". The skills live at the root.

What does **not** depend on the model, and so is the same everywhere: `core/gate.py`, `core/ring.py`,
`core/leak.py`, the pre-commit hook, `tools/ask.py` and `tools/import_chats.py`. They are scripts.
The checks are the safety net: a model that ignores a rule still gets stopped at commit time.

## A rule for every model

Whatever the model, the vault's central rule holds: **nothing is written about you that you did not
say.** A smaller model is more likely to "fill in" your profile. Check `git diff vault/memory/` after
each session, and refuse any line without your own quote.

`[VERIFY: how well each non-Claude model follows the skills; I have not run them, so this guide makes no claim about quality, checked 2026-10-07]`
