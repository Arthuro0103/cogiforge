# install.ps1 - the Windows (PowerShell) twin of install.sh. Activates the hook in this clone and proves it
# works. Fails LOUDLY (exit code != 0).
#
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-Team <handle>]
#
# [VERIFY] Written without access to a Windows machine: it has not been run on real Windows. The CI job
# `windows-latest` in .github/workflows/prova.yml is informational (continue-on-error). See docs/WINDOWS.md.
#
# `core.hooksPath` is local git config: the clone brings the hook on disk, but it only fires after this script.
# The hook itself is a `#!/bin/sh` script: on Windows it is run by the `sh` that ships with Git for Windows,
# and it calls `python3`, so `python3` has to resolve INSIDE that sh (checked below).
param([string]$Team = "")

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Fail([string]$Message) {
    [Console]::Error.WriteLine("")
    [Console]::Error.WriteLine("ERROR: $Message")
    [Console]::Error.WriteLine("The installation was NOT completed: the hook is not active.")
    exit 1
}

# Runs a native command, hides its output, returns its exit code. A missing program is an exit code too.
function Run([string]$Exe, [string[]]$ArgList) {
    # Windows PowerShell 5.1 turns native stderr into a terminating error under "Stop": relax it here only.
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @ArgList *> $null
        return $LASTEXITCODE
    } catch {
        return 127
    }
}

if ($Team -ne "" -and $Team -cnotmatch '^[a-z0-9][a-z0-9_-]*$') {
    Fail "-Team needs a handle of lowercase letters, digits, - or _ (starting with a letter or digit)."
}

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { Fail "git not found in PATH (install Git for Windows)." }
if ((Run "git" @("rev-parse", "--is-inside-work-tree")) -ne 0) {
    Fail "this is not a git repository. Use 'git clone', not the zip, or run 'git init' here."
}

# Python 3.10+: try `python`, then the `py` launcher, then `python3`. The Microsoft Store alias stub exists on
# PATH and prints an install hint instead of running, so each candidate has to RUN a real version check.
$check = "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
$python = $null
$candidates = @(@("python"), @("py", "-3"), @("python3"))
foreach ($c in $candidates) {
    if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
    $rest = @(); if ($c.Length -gt 1) { $rest = $c[1..($c.Length - 1)] }
    if ((Run $c[0] ($rest + @("-c", $check))) -eq 0) { $python = $c; break }
}
if (-not $python) { Fail "Python 3.10 or newer not found (tried python, py -3, python3). Install it from python.org and tick 'Add to PATH'." }
$pyExe = $python[0]
$pyPre = @(); if ($python.Length -gt 1) { $pyPre = $python[1..($python.Length - 1)] }

if (-not (Test-Path -LiteralPath ".githooks/pre-commit")) { Fail ".githooks/pre-commit does not exist." }

# The hook runs under Git for Windows' sh and calls `python3`. Find that sh and ask it.
$sh = Get-Command sh -ErrorAction SilentlyContinue
$shPath = $null
if ($sh) { $shPath = $sh.Source } else {
    $gitDir = Split-Path -Parent (Split-Path -Parent $git.Source)
    foreach ($rel in @("usr\bin\sh.exe", "bin\sh.exe")) {
        $p = Join-Path $gitDir $rel
        if (Test-Path -LiteralPath $p) { $shPath = $p; break }
    }
}
if (-not $shPath) { Fail "no sh found (it ships with Git for Windows). The pre-commit hook needs it." }
if ((Run $shPath @("-c", "python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'")) -ne 0) {
    Fail "the hook calls 'python3' and it does not resolve (as Python 3.10+) inside Git's sh. See docs/WINDOWS.md: either make 'python3' available on PATH, or use WSL."
}

if ((Run "git" @("config", "core.hooksPath", ".githooks")) -ne 0) { Fail "could not write core.hooksPath." }

if ((Run $pyExe ($pyPre + @("core/ring.py", "--selftest"))) -ne 0) {
    & $pyExe @pyPre core/ring.py --selftest
    Fail "the ring selftest failed: the gate does not catch an orphan."
}

# vault/private.txt -> read-deny rules for Claude Code in .claude/settings.json (see docs/PRIVATE.md)
if ((Run $pyExe ($pyPre + @("core/private.py", "--apply"))) -ne 0) {
    & $pyExe @pyPre core/private.py --apply
    Fail "could not write the read-deny rules from vault/private.txt into .claude/settings.json."
}

if ($Team -ne "") {
    $email = (& git config user.email)
    if (-not $email) { Fail "team mode needs your git e-mail: git config user.email you@example.com" }
    if (Test-Path -LiteralPath "vault/roles.txt") { Fail "vault/roles.txt already exists: team mode is on. Ask an admin to add your line." }
    if (-not (Test-Path -LiteralPath "vault/people/_template")) { Fail "vault/people/_template does not exist." }
    New-Item -ItemType Directory -Force -Path "vault/people" | Out-Null
    if (-not (Test-Path -LiteralPath "vault/people/$Team")) { Copy-Item -Recurse -LiteralPath "vault/people/_template" -Destination "vault/people/$Team" }
    # LF line endings on purpose: the Python parsers and the hook read these files
    $roles = "# handle  admin|member  e-mail (matched against git config user.email)`n$Team admin $email`n"
    [IO.File]::WriteAllText((Join-Path $PWD "vault/roles.txt"), $roles, (New-Object Text.UTF8Encoding($false)))
    # the e-mails in roles.txt are deliberate: the leak scanner would block the file, so it is exempted by name
    $ignore = if (Test-Path -LiteralPath ".leakignore") { Get-Content -LiteralPath ".leakignore" } else { @() }
    if ($ignore -notcontains "vault/roles.txt") { [IO.File]::AppendAllText((Join-Path $PWD ".leakignore"), "vault/roles.txt`n") }
    Write-Host "OK - team mode on: you ($Team) are the admin in vault/roles.txt; your folder is vault/people/$Team/."
}

Write-Host "OK - hook active (core.hooksPath=.githooks) and the ring selftest passed."
Write-Host "Test it yourself: create a note without a link in vault/notes/ and run git commit."
exit 0
