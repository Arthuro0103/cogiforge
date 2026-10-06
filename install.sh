#!/bin/sh
# install.sh — activates the hook in this clone and proves it works. Fails LOUDLY (rc != 0).
#
# `core.hooksPath` is local git config: the clone brings the hook on disk, but it only fires
# after this script. Without it the protection exists and does not protect.

cd "$(dirname "$0")" || exit 1

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

echo "OK — hook active (core.hooksPath=.githooks) and the ring selftest passed."
echo "Test it yourself: create a note without a link in vault/notes/ and run git commit."
