# Folders Claude Code is told not to read

The leak hook stops a secret from being **written** into a commit. It does not stop Claude from **reading**
a file and quoting it back. This guide covers the second half, and says plainly where it stops working.

## How it works

1. `vault/private.txt` lists one path or glob per line, relative to `vault/`. `#` starts a comment. The
   template ships with `people/*/private/**`.
2. `sh install.sh` (or `install.ps1` on Windows) turns each line into a Claude Code permission rule in
   `.claude/settings.json`: the line `people/*/private/**` becomes `Read(/vault/people/*/private/**)` under
   `permissions.deny`.
3. Run the installer again after you edit `private.txt`. It is idempotent: it adds missing rules, never
   duplicates one, and never removes a rule you already had. A rule you delete from `private.txt` stays in
   `settings.json` until you delete it there by hand.
4. If `.claude/settings.json` is not valid JSON, or has an unexpected shape, the installer stops with an error
   and leaves the file as it was. Fix it by hand and run the installer again.
5. `python3 core/private.py --check` exits 1 if a rule derived from `private.txt` is missing in the settings.

Glob rules, from the Claude Code permissions documentation (read 2026-10-07):

- The rule has gitignore syntax. `*` matches inside one path segment; `**` matches across directories.
- A leading `/` anchors the path at the project root for rules in `.claude/settings.json`. That is why the
  installer writes `/vault/...`. It assumes you start Claude Code at the repo root, as the Quickstart says.
- `private.txt` lines may not start with `/`, `~` or `!`, contain `..`, a backslash or a drive letter: the
  installer refuses them rather than guess.

`[VERIFY 2026-10-07]` These rules come from reading the public documentation, not from a test against every
Claude Code version. The documentation ties some deny-rule behaviors to specific versions (for example,
blocking Edit and Write on a path covered by a Read rule). After you change `private.txt`, test it in your own
installation: ask Claude to read a file the rule covers and check that it refuses.

## The limit, with all the letters

This works for **Claude Code's own file tools**, and that is all it works for.

- It is **not a boundary against Bash**. The documentation says deny rules cover file commands Claude Code
  recognizes (`cat`, `head`, `tail`, `sed`, `tee`) and redirections, but not a command that reads files
  without naming them (`grep -r pattern .` from inside the folder), nor a script that opens files itself. A
  model that wants the content and has a shell can usually get it. Only the OS-level sandbox blocks that.
- It is **not a boundary against other agents**. Codex, Cursor, Gemini CLI, Copilot and any other tool read
  `AGENTS.md`, not `.claude/settings.json`, and ignore these rules.
- It is **not a boundary against whoever clones the repo**. Anything committed is readable by everyone who has
  the repo. The rules only shape what Claude does on this machine.
- The documentation calls Read rules a **best-effort** block for tools such as Grep and Glob.

What actually keeps something private:

- Put intimate material in `vault/people/<handle>/private/`. It is **gitignored**, so it never enters the repo.
- For anything that must not reach a model at all, use a **separate vault** that this repo never sees.

The deny rule is a seatbelt for honest mistakes, not a lock.
