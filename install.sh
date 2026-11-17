#!/bin/sh
# install.sh — activates the hook in this clone and proves it works. Fails LOUDLY (rc != 0).
#
# `core.hooksPath` is local git config: the clone brings the hook on disk, but it only fires
# after this script. Without it the protection exists and does not protect.

cd "$(dirname "$0")" || exit 1

# `sh install.sh --team <handle>` also turns on team mode (see README, "Teams and schools"); without the
# flag nothing here changes.
TEAM=""
if [ "$1" = "--team" ]; then
    TEAM="$2"
    printf '%s' "$TEAM" | LC_ALL=C grep -Eq '^[a-z0-9][a-z0-9_-]*$' \
        || { echo "ERROR: --team needs a handle of lowercase letters, digits, - or _ (starting with a letter or digit)." >&2; exit 1; }
elif [ -n "$1" ]; then
    echo "ERROR: unknown argument '$1'. Usage: sh install.sh [--team <handle>]" >&2
    exit 1
fi

fail() {
    echo "" >&2
    echo "ERROR: $*" >&2
    echo "The installation was NOT completed: the hook is not active." >&2
    exit 1
}

command -v git >/dev/null 2>&1 || fail "git not found in PATH."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || fail "this is not a git repository. Use 'git clone', not the zip, or run 'git init' here."
command -v python3 >/dev/null 2>&1 || fail "python3 not found in PATH (it needs to be 3.10 or newer)."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || fail "Python 3.10 or newer is required; found $(python3 -V 2>&1)."
[ -f .githooks/pre-commit ] || fail ".githooks/pre-commit does not exist."

chmod +x .githooks/pre-commit || fail "could not make .githooks/pre-commit executable."
git config core.hooksPath .githooks || fail "could not write core.hooksPath."

python3 core/ring.py --selftest >/dev/null 2>&1 \
    || { python3 core/ring.py --selftest >&2; fail "the ring selftest failed: the gate does not catch an orphan."; }

# vault/private.txt -> read-deny rules for Claude Code in .claude/settings.json (idempotent; a malformed
# settings file is an error here, never overwritten). See docs/PRIVATE.md for what this does NOT cover.
python3 core/private.py --apply >/dev/null || { python3 core/private.py --apply >&2; fail "could not write the read-deny rules from vault/private.txt into .claude/settings.json."; }

if [ -n "$TEAM" ]; then
    email=$(git config user.email)
    [ -n "$email" ] || fail "team mode needs your git e-mail: git config user.email you@example.com"
    [ -f vault/roles.txt ] && fail "vault/roles.txt already exists: team mode is on. Ask an admin to add your line."
    [ -d vault/people/_template ] || fail "vault/people/_template does not exist."
    mkdir -p vault/people
    [ -e "vault/people/$TEAM" ] || cp -R vault/people/_template "vault/people/$TEAM" || fail "could not create vault/people/$TEAM."
    printf '# handle  admin|member  e-mail (matched against git config user.email)\n%s admin %s\n' "$TEAM" "$email" > vault/roles.txt \
        || fail "could not write vault/roles.txt."
    # the e-mails in roles.txt are deliberate: the leak scanner would block the file, so it is exempted by name
    grep -qxF 'vault/roles.txt' .leakignore 2>/dev/null || printf 'vault/roles.txt\n' >> .leakignore
    echo "OK — team mode on: you ($TEAM) are the admin in vault/roles.txt; your folder is vault/people/$TEAM/."
    echo "Add members as lines in vault/roles.txt. Intimate material goes in vault/people/$TEAM/private/ (gitignored)."
fi

# Other agents look for skills in `.agents/skills` (Codex, Gemini CLI; see docs/USING-OTHER-MODELS.md).
# Link it to `.claude/skills` so they find the same files. This step runs last, never replaces or deletes
# what is already there, never writes through a `.agents` that is itself a link, and a failure here does
# not undo the hook: it only prints a note.
same_dir() { [ -d "$1" ] && [ -d "$2" ] && [ "$(cd -P "$1" 2>/dev/null && pwd -P)" = "$(cd -P "$2" 2>/dev/null && pwd -P)" ]; }
AGENTS_LINK=""
if same_dir .agents/skills .claude/skills; then
    AGENTS_LINK="ok"
elif [ -L .agents ] || [ -L .agents/skills ] || [ -e .agents/skills ]; then
    AGENTS_LINK="kept"
elif mkdir -p .agents 2>/dev/null && ln -s ../.claude/skills .agents/skills 2>/dev/null && same_dir .agents/skills .claude/skills; then
    AGENTS_LINK="ok"
    # the link is local to this clone: hide it from git here, not in .gitignore, so a `.agents/skills`
    # that the user makes on their own is never hidden
    excl=$(git rev-parse --git-path info/exclude 2>/dev/null)
    if [ -n "$excl" ]; then
        mkdir -p "$(dirname "$excl")" 2>/dev/null
        grep -qxF '/.agents/skills' "$excl" 2>/dev/null || printf '/.agents/skills\n' >> "$excl" 2>/dev/null
    fi
else
    AGENTS_LINK="failed"
fi

echo "OK — hook active (core.hooksPath=.githooks) and the ring selftest passed."
[ -f vault/private.txt ] && echo "Claude Code read-deny rules from vault/private.txt are in .claude/settings.json."
case "$AGENTS_LINK" in
    ok)     echo "Skills for other agents: .agents/skills is linked to .claude/skills (Codex and Gemini CLI look there)." ;;
    kept)   echo "NOTE: .agents or .agents/skills already exists and is not this repo's link, so it was left alone. Codex and Gemini CLI will not find these skills there." ;;
    failed) echo "NOTE: the skills link for other agents was not created. Codex and Gemini CLI will not find the skills on their own; see docs/USING-OTHER-MODELS.md." ;;
esac
echo "Test it yourself: create a note without a link in vault/notes/ and run git commit."
