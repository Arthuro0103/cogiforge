#!/usr/bin/env python3
"""skill_trigger.py: does a model pick the right skill from its `description:` alone?

Reads a JSON file of prompts (`[{"id", "prompt", "expect": "<skill>" or null}]`), runs a model once per
prompt in a throwaway COPY of the repo (so a skill never writes into your worktree), with the write and shell
tools denied, and records the first call of the `Skill` tool in the stream. Prints a hit or a miss per prompt,
the total of hits, and the false triggers (a skill called where `expect` is null).

Use it before and after you shorten a description: hits must not drop, false triggers must not rise.

COST: one model call per prompt (the default is Haiku, a few turns each). It is NOT run by the tests or by CI.
Isolation: `--setting-sources project` keeps your personal skills and settings out; plugins and built-in
skills of the installed Claude Code still load, so use the same machine for the before and the after.

    python3 tools/skill_trigger.py tests/skill_prompts.json
    python3 tools/skill_trigger.py tests/skill_prompts.json --only cf-study --jobs 2
    python3 tools/skill_trigger.py tests/skill_prompts.json --cmd "claude -p --model sonnet --output-format stream-json --verbose --max-turns 2"
rc: 0 every prompt hit, no false trigger · 1 some miss or false trigger · 2 usage · 3 NOT_VERIFIED (a run failed to produce a stream)
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CMD = "claude -p --model haiku --output-format stream-json --verbose --max-turns 2"
ISOLATION = ["--setting-sources", "project", "--strict-mcp-config", "--disallowedTools", "Bash,Edit,Write,NotebookEdit"]
ROOT = Path(__file__).resolve().parent.parent


def first_skill(stream: str) -> tuple[str | None, bool]:
    """(name of the first Skill call or None, whether the stream held any assistant or result event)."""
    seen = False
    for line in stream.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") in ("assistant", "result"):
            seen = True
        if ev.get("type") != "assistant":
            continue
        content = (ev.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                name = (block.get("input") or {}).get("skill")
                return (str(name).split(":")[-1] if name else None), True
    return None, seen


def run_one(item: dict, cmd: list[str], workdir: Path, timeout: int) -> dict:
    try:
        p = subprocess.run(cmd + ISOLATION + ["--", item["prompt"]], cwd=workdir, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=timeout)
        got, seen = first_skill(p.stdout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"id": item["id"], "expect": item.get("expect"), "got": None, "ok": None, "error": type(exc).__name__}
    if not seen:
        return {"id": item["id"], "expect": item.get("expect"), "got": None, "ok": None, "error": "no stream"}
    return {"id": item["id"], "expect": item.get("expect"), "got": got, "ok": got == item.get("expect"), "error": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prompts", help="JSON file of prompts")
    ap.add_argument("--cmd", default=CMD, help="the model command (default: %(default)s)")
    ap.add_argument("--only", help="run only the prompts whose expect (or id) contains this text")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--root", default=str(ROOT), help="the repo to copy (default: this one)")
    args = ap.parse_args(argv)
    try:
        items = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
        assert isinstance(items, list) and all("id" in i and "prompt" in i for i in items)
    except (OSError, ValueError, AssertionError) as exc:
        print(f"usage: cannot read prompts: {exc}", file=sys.stderr)
        return 2
    if args.only:
        items = [i for i in items if args.only in (i.get("expect") or "") or args.only in i["id"]]
    cmd = shlex.split(args.cmd)
    if shutil.which(cmd[0]) is None:
        print(f"usage: {cmd[0]} not found", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="skill-trigger-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(args.root, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            results = list(ex.map(lambda i: run_one(i, cmd, work, args.timeout), items))
    for r in results:
        tag = "ERROR" if r["ok"] is None else ("HIT " if r["ok"] and r["expect"] else "OK  " if r["ok"] else "MISS" if r["expect"] else "FALSE")
        print(f"{tag} {r['id']:<16} expect={r['expect']} got={r['got']}" + (f"  ({r['error']})" if r["error"] else ""))
    expected = [r for r in results if r["expect"]]
    nulls = [r for r in results if not r["expect"]]
    hits = sum(1 for r in expected if r["ok"])
    false = sum(1 for r in nulls if r["ok"] is False)
    errors = sum(1 for r in results if r["ok"] is None)
    print(f"hits {hits}/{len(expected)} · false triggers {false}/{len(nulls)} · errors {errors}")
    if errors:
        print("NOT_VERIFIED: some runs produced no stream; the totals above are not a measurement")
        return 3
    return 0 if hits == len(expected) and not false else 1


if __name__ == "__main__":
    sys.exit(main())
