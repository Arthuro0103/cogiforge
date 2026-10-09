#!/usr/bin/env python3
"""bench.py: time and peak memory of each cogiforge tool on a synthetic vault of N notes. Stdlib only.

    python3 tools/bench.py --sizes 1000 5000 10000 [--runs 3] [--out table.md] [--keep DIR]

Each tool runs as a child process, in the foreground, at normal priority (a low priority would flatter
the number). Wall time is the median of --runs, and the CPU time (user + system) is printed next to it because
wall time grows when the machine is busy with other work and CPU time mostly does not; peak memory is the child's maximum resident set size
(`resource.getrusage(RUSAGE_CHILDREN)` in a fresh child, so one run never inflates the next).

What is measured, per size:
  gate        core/gate.py --vault V
  ring        core/ring.py --vault V --gate
  hub         tools/hub.py --check --vault V
  search      tools/ask.py search <query>
  cite        tools/ask.py cite <answer with 5 citations>
  import      tools/import.py <the vault> --dry-run   (the plan for the whole vault, writes nothing)
  leak        core/leak.py <the vault>
  usage       tools/usage.py --vault V
  context     core/budget.py --vault V --root R (bytes a session loads; R holds this checkout's CLAUDE.md and skills)
  pre-commit  .githooks/pre-commit with ONE new linked note staged, in a throwaway git repo, whose notes are an
              hour old like a real vault's; reported twice: `cold` (no edge cache yet: the first commit after a clone)
              and `warm` (the edge cache that core/ring.py keeps inside .git, which is every commit after that)

A tool that does not exist yet in this checkout is reported as `missing`, never as fast.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth  # noqa: E402

CHILD = r"""
import resource, subprocess, sys, time, json
t = time.perf_counter()
p = subprocess.run(json.loads(sys.argv[1]), cwd=sys.argv[2], capture_output=True, text=True)
dt = time.perf_counter() - t
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
print(json.dumps({"rc": p.returncode, "s": dt, "cpu": ru.ru_utime + ru.ru_stime, "rss": ru.ru_maxrss, "tail": (p.stdout + p.stderr)[-200:]}))
"""


def measure(cmd: list[str], cwd: Path, env: dict | None = None) -> dict:
    p = subprocess.run([sys.executable, "-c", CHILD, json.dumps(cmd), str(cwd)], capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    r = json.loads(p.stdout)
    # ru_maxrss is bytes on macOS and kilobytes on Linux
    r["rss_mb"] = r["rss"] / (1024 * 1024 if sys.platform == "darwin" else 1024)
    return r


def median_run(cmd, cwd, runs, env=None, prepare=None):
    rows = []
    for _ in range(runs):
        if prepare:
            prepare()
        rows.append(measure(cmd, cwd, env))
    return {"rc": rows[-1]["rc"], "s": statistics.median(r["s"] for r in rows), "cpu": statistics.median(r["cpu"] for r in rows),
            "mb": max(r["rss_mb"] for r in rows), "tail": rows[-1]["tail"]}


def machine() -> str:
    mem = ""
    try:
        mem = f", {int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True).stdout) // 2**30} GB"
    except (ValueError, OSError):
        pass
    return f"{platform.platform()}, {platform.machine()}, Python {platform.python_version()}{mem}"


def commit_repo(vault: Path, work: Path) -> Path:
    """A throwaway repo: this checkout's core/ and hook plus the synthetic vault, all committed once."""
    repo = work / "repo"
    repo.mkdir()
    shutil.copytree(ROOT / "core", repo / "core", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / ".githooks", repo / ".githooks")
    shutil.copytree(vault, repo / "vault")
    old = time.time() - 3600           # a real vault is old; a file changed in the last 2 s is never cached on purpose
    for p in (repo / "vault").rglob("*"):
        os.utime(p, (old, old))
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "bench@example.com")
    git("config", "user.name", "bench")
    git("config", "core.hooksPath", ".githooks")
    git("add", "-A")
    git("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "synthetic vault")
    return repo


def stage_one_note(repo: Path) -> None:
    subprocess.run(["git", "reset", "-q", "--hard"], cwd=repo, check=True, capture_output=True)
    note = repo / "vault/notes/learning/one-new-note.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    target = next(iter(sorted((repo / "vault/notes/learning").glob("a-*.md"))), None)
    link = f"[[{target.relative_to(repo / 'vault').with_suffix('').as_posix()}]]" if target else "[[home]]"
    note.write_text("---\ntype: note\narea: learning\ndate: 2026-10-01\ntarget: none\n---\n# One new note links its neighbor\n\n"
                    f"The new idea builds on {link} in the middle of the text.\n", encoding="utf-8")
    subprocess.run(["git", "add", "vault/notes/learning/one-new-note.md"], cwd=repo, check=True, capture_output=True)


def bench_size(n: int, runs: int, work: Path) -> dict:
    out = work / f"v{n}"
    synth.generate(out, n, 7)
    vault = out / "vault"
    shutil.copy(ROOT / "CLAUDE.md", out / "CLAUDE.md")  # the fixed part of what a session loads is this checkout's own
    shutil.copy(ROOT / "vault" / "CLAUDE.md", vault / "CLAUDE.md")
    with (vault / "home.md").open("a", encoding="utf-8") as fh:
        fh.write("\n- [[CLAUDE]]\n")  # a real vault links its manual; without an edge it would be an orphan
    shutil.copytree(ROOT / ".claude" / "skills", out / ".claude" / "skills")
    first = sorted((vault / "notes").rglob("*.md"))[:5]
    answer = work / f"answer-{n}.md"
    answer.write_text("\n".join(f"Claim {i}. [[{p.relative_to(vault).with_suffix('').as_posix()}]]" for i, p in enumerate(first)) + "\n")
    py = sys.executable
    empty = work / f"empty-{n}"          # the import plans a copy of the whole vault into a vault that is not the source
    empty.mkdir()
    env = {"LEAK_BLOCKLIST": str(work / "absent.txt")}
    tools = {
        "gate": ([py, "core/gate.py", "--vault", str(vault)], None),
        "ring": ([py, "core/ring.py", "--vault", str(vault), "--gate"], None),
        "hub": ([py, "tools/hub.py", "--check", "--vault", str(vault)], None),
        "search": ([py, "tools/ask.py", "search", "slow budget habit", "--vault", str(vault)], None),
        "cite": ([py, "tools/ask.py", "cite", str(answer), "--vault", str(vault)], None),
        "import": ([py, "tools/import.py", str(vault), "--vault", str(empty), "--dry-run"], None),
        "leak": ([py, "core/leak.py", str(vault)], env),
        "usage": ([py, "tools/usage.py", "--vault", str(vault)], None),
        "context": ([py, "core/budget.py", "--vault", str(vault), "--root", str(out)], None),
    }
    result = {}
    for name, (cmd, e) in tools.items():
        script = Path(cmd[1])
        if not (ROOT / script).is_file():
            result[name] = {"missing": True}
            continue
        result[name] = median_run(cmd, ROOT, runs, e)
    (work / f"r{n}").mkdir()
    repo = commit_repo(vault, work / f"r{n}")
    cache = repo / ".git" / "cogiforge-edges.json"
    cache.unlink(missing_ok=True)
    result["pre-commit (cold)"] = median_run(["sh", ".githooks/pre-commit"], repo, 1, env, prepare=lambda: stage_one_note(repo))
    result["pre-commit (warm)"] = median_run(["sh", ".githooks/pre-commit"], repo, runs, env, prepare=lambda: stage_one_note(repo))
    return result


def table(sizes: list[int], data: dict[int, dict]) -> str:
    names = list(data[sizes[0]])
    lines = ["| tool | " + " | ".join(f"{n:,} notes" for n in sizes) + " |", "|---|" + "---|" * len(sizes)]
    for name in names:
        cells = []
        for n in sizes:
            r = data[n][name]
            cells.append("missing" if r.get("missing") else f"{r['s']:.2f} s ({r['cpu']:.2f} cpu), {r['mb']:.0f} MB" + ("" if r["rc"] in (0,) else f" (rc {r['rc']})"))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sizes", type=int, nargs="+", default=[1000, 5000, 10000])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out")
    ap.add_argument("--keep", help="build the vaults in this folder and keep them")
    a = ap.parse_args(argv)
    data = {}
    with tempfile.TemporaryDirectory(prefix="cogiforge-bench-") as td:
        work = Path(a.keep) if a.keep else Path(td)
        work.mkdir(parents=True, exist_ok=True)
        for n in a.sizes:
            print(f"measuring {n} notes ...", file=sys.stderr)
            data[n] = bench_size(n, a.runs, work)
    load = ", ".join(f"{x:.1f}" for x in os.getloadavg())
    text = (f"Machine: {machine()}. Median of {a.runs} runs, foreground, normal priority; load average {load} when it finished. "
            f"Each cell is wall time (CPU time of the child) and peak memory.\n\n") + table(a.sizes, data) + "\n"
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
