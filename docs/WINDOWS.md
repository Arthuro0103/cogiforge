# Windows

Status: **not verified on real Windows.** The author could not run Windows when writing this. Everything below
that depends on Windows behavior is marked `[VERIFY]` (as of 2026-10-07) and should be treated as a claim
to check, not a promise. The CI has an informational `windows-latest` job (`continue-on-error`): a red run
there does not fail the project, and a green run there is the only evidence that exists.

## Native path (PowerShell)

You need Git for Windows and Python 3.10 or newer.

```powershell
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
powershell -ExecutionPolicy Bypass -File install.ps1
```

`install.ps1` does what `install.sh` does: checks git and Python 3.10+, sets `core.hooksPath` to `.githooks`,
runs the ring selftest, writes the Claude Code read rules from `vault/private.txt` (see
[PRIVATE.md](PRIVATE.md)), and exits with a non-zero code on any failure. `-Team <handle>` turns team mode on.

Why this should work, and what to check:

- The hook `.githooks/pre-commit` is a `#!/bin/sh` script. Git for Windows ships its own `sh` and is expected to
  run hooks through it. `[VERIFY]` that a commit in your clone runs the hook (create a note without a link in
  `vault/notes/` and commit: it must be blocked).
- The hook calls `python3`, not `python`. On Windows the installer usually registers `python.exe`, and `python3`
  may be missing or may be the Microsoft Store stub that opens the Store. `install.ps1` therefore asks Git's `sh`
  whether `python3` runs as Python 3.10+, and fails if not. Fix: put a real `python3` on `PATH` (for example copy
  `python.exe` to `python3.exe` in the same folder, or use a venv that has both). `[VERIFY]`
- The installer finds Python by trying `python`, then `py -3`, then `python3`, and runs each one, because the
  Store stub is on `PATH` but does not run.
- Line endings: `.gitattributes` does not exist in this repo. If Git for Windows checks files out with CRLF
  (`core.autocrlf=true`), a shell hook with CRLF line endings fails with an odd "command not found" error.
  `[VERIFY]` If you see that, run `git config core.autocrlf input` and check the hook out again.
- Claude Code deny rules on Windows: the documentation says paths are normalized to POSIX form before matching.
  The rules the installer writes are project-relative (`/vault/...`), which should not depend on the drive.
  `[VERIFY]`

## WSL path

If the native path gives trouble, use WSL: open a WSL shell, clone the repo **inside the Linux file system**
(for example under `~/`, not under `/mnt/c/`), and follow the normal Quickstart with `sh install.sh`. That is the
same environment as Linux, which is covered by the CI. Run Claude Code and Obsidian so that both see the same
folder. `[VERIFY]` opening a vault that lives in the WSL file system from Windows Obsidian.

## What is not claimed

- No claim that the full test suite passes on Windows. Some tests start `sh` and `git` processes and assume
  POSIX paths. `[VERIFY]` through the CI job.
- No claim about the rest of the tools (`tools/`) on Windows.
