# Shared mode (teams, schools)

Shared mode is on only when `roles.txt` exists in `vault/`; without it, ignore this section.
`vault/roles.txt` has one line per person: `handle  admin|member  email`.

- **Who am I talking to:** the e-mail from `git config user.email`, looked up in `roles.txt`. Not listed: say so and tell them to ask an admin for a line; write nothing.
- **Memory rule:** the rule below ("nothing claims something about the user that they did not say") applies to `people/<handle>/` of whoever is talking, which replaces `memory/` for them (`people/<handle>/memory/{profile,patterns,decisions}.md`, `inbox/`, `diary/`).
- **Never read another person's folder** (`people/<other>/`) to answer a question, not even to "help". `people/<handle>/private/` is gitignored: it is the only place for what is intimate.
- `private.txt` lists folders that Claude Code is told not to read (rules in `.claude/settings.json`, made by the installer); it is not a boundary against Bash, other agents or clones: see `docs/PRIVATE.md`.
- **Tasks** stay in the shared `tasks/`, with an `owner: <handle>` field in the header.
- **Roles:** a member does not edit `roles.txt` or `areas.txt`, nor create a `projects/<new>/instructions.md`; the pre-commit hook blocks it. That is a convention, not security: real enforcement is CODEOWNERS plus branch protection on the host.
