#!/usr/bin/env python3
"""agents_watch.py: did a background subagent stop without finishing? Stdlib only.

    python3 tools/agents_watch.py [--session current|<id prefix>|<dir>] [--min 10] [--root DIR] [--json]
    python3 tools/agents_watch.py --selftest

The failure behind it: a subagent launched in the background said "waiting for the render" and stopped. The render
had already ended, nothing ran for 13 minutes to over an hour, and nobody noticed until the main session looked at
the clock. Its transcript was not growing and no worker process was alive.

Where the data is: `<root>/<project slug>/<session>/subagents/agent-<id>.jsonl` (plus `agent-<id>.meta.json` with the
description). The default root is `~/.claude/projects`. Only the tail of each transcript is read, and `ps` is read
once. Nothing is killed or written.

States (a typed verdict; NOT_VERIFIED is never OK):
  RUNNING           the transcript grew less than --min minutes ago, OR a worker process is using CPU (> 5%)
  STOPPED           not finished, transcript idle for >= --min minutes, no worker process      <- ALARM
  FINISHED          the last entry is a final result (stop_reason end_turn, or a SubagentStop event)
  MISSING_ARTIFACT  FINISHED, but the final message says it saved a file that does not exist or has 0 bytes  <- ALARM
  NOT_VERIFIED      could not be read (missing, empty, unreadable); or the promised file is not materialized /
                    is a relative path with no base; or the process list is unavailable (no `ps`, Windows) and
                    the transcript is idle, so "stopped" cannot be told from "busy"

rc: 0 no alarm · 1 some STOPPED or MISSING_ARTIFACT · 2 usage · 3 nothing could be read (every agent NOT_VERIFIED, or
no subagents found).

A limit, stated and not hidden: a process is matched by NAME (ffmpeg, remotion, chrome-headless-shell) to any
unfinished agent, because there is no way to know whose it is; python and node count only when the agent's id or a
path from the end of its transcript appears in the command line. A leftover tool process at ~0% CPU does not count
as alive.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
CPU_MIN = 5.0
TAIL = 256 * 1024
WORK_NAMES = ("ffmpeg", "remotion", "chrome-headless-shell")
GENERIC = ("python", "node")
RUNNING, STOPPED, FINISHED, NV = "RUNNING", "STOPPED", "FINISHED", "NOT_VERIFIED"
MISSING = "MISSING_ARTIFACT"
DATALESS = 0x40000000  # SF_DATALESS (macOS cloud placeholder)
_STAT = os.stat  # replaceable in the selftest (a placeholder file cannot be made for real)
# a sentence that says a file was WRITTEN; a path that is only read or mentioned outside such a sentence is ignored
PROMISE = re.compile(r"\b(wrote|written|saved|created|generated|saving|writing to)\b|\bfile\s*:|\boutput\s*:", re.I)
EXT = re.compile(r"\.[A-Za-z0-9]{1,8}$")
ABS_PATH = re.compile(r"/(?:[\w.~-]+/){2,}[^\s'\"`)\\]+")


def read_tail(p: Path, n: int = TAIL) -> list[dict]:
    """Last entries of the jsonl, without reading the whole file. Raises OSError/ValueError."""
    size = p.stat().st_size
    if size == 0:
        raise ValueError("empty transcript")
    with open(p, "rb") as f:
        if size > n:
            f.seek(size - n)
            f.readline()  # drop the cut line
        raw = f.read().decode("utf-8", "replace").splitlines()
    out = []
    for line in raw:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not out:
        raise ValueError("no readable JSON line in the tail")
    return out


def finished(entries: list[dict]) -> bool:
    for e in reversed(entries):
        if (e.get("attachment") or {}).get("hookEvent") == "SubagentStop":
            return True
        m = e.get("message")
        if e.get("type") == "assistant" and isinstance(m, dict):
            return m.get("stop_reason") == "end_turn"
        if e.get("type") in ("assistant", "user"):
            return False
    return False


def last_signal(entries: list[dict]) -> tuple[str, str, list[str]]:
    """(last tool, snippet of the last text <= 120 chars, absolute paths cited in the tail)."""
    tool, text, paths = "", "", []
    for e in entries:
        m = e.get("message")
        if e.get("type") != "assistant" or not isinstance(m, dict) or not isinstance(m.get("content"), list):
            continue
        for b in m["content"]:
            if b.get("type") == "tool_use":
                tool = b.get("name", "")
                paths += ABS_PATH.findall(json.dumps(b.get("input", {})))
            elif b.get("type") == "text" and b.get("text", "").strip():
                text = " ".join(b["text"].split())
    parents = {c.rsplit("/", 1)[0] for c in paths if c.count("/") >= 4}
    return tool, text[:120], sorted(set(paths[-20:]) | parents)


def final_text(entries: list[dict]) -> str:
    """Full text of the last assistant text block in the tail ('' if none)."""
    for e in reversed(entries):
        m = e.get("message")
        if e.get("type") == "assistant" and isinstance(m, dict) and isinstance(m.get("content"), list):
            for b in reversed(m["content"]):
                if b.get("type") == "text" and b.get("text", "").strip():
                    return b["text"]
    return ""


def promised_paths(text: str) -> list[str]:
    """Paths in sentences that say something was written. Inside backticks a space is allowed."""
    found: list[str] = []
    for seg in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n", text):
        if not PROMISE.search(seg):
            continue
        cand = re.findall(r"`([^`]+)`", seg)
        cand += re.sub(r"`[^`]+`", " ", seg).split()
        for t in cand:
            t = t.strip().strip("*\"'()[]<>,;:").rstrip(".")
            if ("/" in t or t.startswith("~")) and EXT.search(t) and not t.startswith(("http:", "https:")):
                found.append(t)
    return list(dict.fromkeys(found))


def check_artifact(c: str) -> tuple[str, str]:
    """('OK'|'MISSING'|'EMPTY'|'NV', reason). A placeholder or a relative path is never missing and never OK."""
    if not (c.startswith("/") or c.startswith("~")):
        return "NV", "relative path with no known base"
    try:
        st = _STAT(os.path.expanduser(c))
    except FileNotFoundError:
        return "MISSING", "does not exist"
    except OSError as ex:
        return "NV", f"{type(ex).__name__}: {ex}"
    if (getattr(st, "st_flags", 0) & DATALESS) or (st.st_size > 0 and getattr(st, "st_blocks", 1) == 0):
        return "NV", "cloud placeholder (not downloaded)"
    if st.st_size == 0:
        return "EMPTY", "0 bytes"
    return "OK", ""


def judge_artifacts(entries: list[dict]) -> tuple[str, list[dict]]:
    """State of a finished agent: MISSING > NOT_VERIFIED > FINISHED, plus the list that was checked."""
    res = []
    for c in promised_paths(final_text(entries)):
        v, why = check_artifact(c)
        res.append({"path": c, "verdict": v, "reason": why})
    if any(x["verdict"] in ("MISSING", "EMPTY") for x in res):
        return MISSING, res
    if any(x["verdict"] == "NV" for x in res):
        return NV, res
    return FINISHED, res


def processes() -> list[dict] | None:
    """[{pid, cpu, cmd}] from `ps`, or None when it cannot be asked (Windows, no `ps`, a failure)."""
    if os.name == "nt":
        return None
    try:
        r = subprocess.run(["ps", "-axo", "pid=,pcpu=,command="], capture_output=True, text=True, check=False, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = []
    for line in r.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3:
            try:
                out.append({"pid": int(parts[0]), "cpu": float(parts[1].replace(",", ".")), "cmd": parts[2]})
            except ValueError:
                pass
    return out


def agent_procs(ps: list[dict], agent_id: str, paths: list[str]) -> list[dict]:
    hits = []
    for p in ps:
        if p["cpu"] <= CPU_MIN:
            continue
        cmd = p["cmd"]
        exe = cmd.split()[0].rsplit("/", 1)[-1].lower()
        if any(n in cmd.lower() for n in WORK_NAMES) or \
           (any(exe.startswith(g) for g in GENERIC) and (agent_id in cmd or any(c in cmd for c in paths))):
            hits.append(p)
    return hits


def evaluate(path: Path, now: float, minutes: int, ps: list[dict] | None) -> dict:
    aid = path.stem.removeprefix("agent-")
    r = {"agent": aid, "description": "", "state": NV, "idle_min": None, "tool": "", "text": "", "processes": [], "reason": ""}
    try:
        r["description"] = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8")).get("description", "")[:60]
    except (OSError, ValueError, AttributeError):
        pass
    try:
        entries = read_tail(path)
        idle = (now - path.stat().st_mtime) / 60
    except (OSError, ValueError) as ex:
        r["reason"] = f"{type(ex).__name__}: {ex}"
        return r
    r["idle_min"] = round(idle, 1)
    r["tool"], r["text"], paths = last_signal(entries)
    if finished(entries):
        r["state"], r["artifacts"] = judge_artifacts(entries)
        r["reason"] = "; ".join(f"{x['path']} ({x['reason']})" for x in r["artifacts"] if x["verdict"] != "OK")
        return r
    if idle < minutes:
        r["state"] = RUNNING
        return r
    if ps is None:
        r["reason"] = "idle transcript, but the process list is unavailable, so stopped cannot be told from busy"
        return r
    r["processes"] = [{"pid": p["pid"], "cpu": p["cpu"], "cmd": p["cmd"][:80]} for p in agent_procs(ps, aid, paths)]
    r["state"] = RUNNING if r["processes"] else STOPPED
    return r


def find_session(target: str, root: Path = ROOT, cwd: Path | None = None) -> Path:
    """Session folder (the one with subagents/). 'current' = newest session of the project whose cwd is this one."""
    if target == "current":
        slug = re.sub(r"[^A-Za-z0-9]", "-", str((cwd or Path.cwd()).resolve()))
        folder = root / slug[:200] if len(slug) > 200 else root / slug  # a name over 255 would raise on stat
        if len(slug) > 200:
            # Claude Code truncates a long project folder name to the first 200 characters + "-<hash>"
            # (rule read in binary 2.1.331; the hash is not reproduced here, so match by prefix)
            cands = sorted(d for d in root.glob(slug[:200] + "-*") if d.is_dir())
            if len(cands) > 1:
                raise FileNotFoundError(
                    f"ambiguous: {len(cands)} project folders share the truncated name of this directory under {root}; pass --session")
            folder = cands[0] if cands else root / "-no-such-project-folder"
        sessions = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
        if not sessions:
            raise FileNotFoundError(f"no session transcript for this directory under {root}; pass --session")
        return folder / sessions[0].stem
    p = Path(target)
    if p.is_dir():
        return p
    found = sorted(d for d in root.glob(f"*/{target}*") if d.is_dir())
    if not found:
        raise FileNotFoundError(f"session not found: {target}")
    return found[0]


def scan(folder: Path, minutes: int, now: float | None = None, ps: list[dict] | None | str = "read") -> list[dict]:
    now = time.time() if now is None else now
    files = sorted((folder / "subagents").glob("agent-*.jsonl"))
    if isinstance(ps, str):
        ps = processes()
    return [evaluate(f, now, minutes, ps) for f in files]


def exit_code(rs: list[dict]) -> int:
    if not rs or all(r["state"] == NV for r in rs):
        return 3
    return 1 if any(r["state"] in (STOPPED, MISSING) for r in rs) else 0


def show(rs: list[dict]) -> None:
    order = {STOPPED: 0, MISSING: 0, NV: 1, RUNNING: 2, FINISHED: 3}
    for r in sorted(rs, key=lambda r: (order[r["state"]], -(r["idle_min"] or 0))):
        if r["state"] == FINISHED:
            continue
        idle = f"{r['idle_min']:.0f}min" if r["idle_min"] is not None else "-"
        print(f"{r['state']:<16} {r['agent'][:10]:<10} {idle:>7}  proc={len(r['processes'])}  "
              f"{r['tool'] or '-':<10} {r['description'] or r['reason']}")
        if r["text"]:
            print(f"{'':<15} -> {r['text']}")
    n = {s: sum(r["state"] == s for r in rs) for s in (STOPPED, MISSING, RUNNING, FINISHED, NV)}
    print(f"-- {len(rs)} agents: " + " | ".join(f"{v} {k}" for k, v in n.items()))


def _write(p: Path, entries: list[dict], idle_min: float) -> None:
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    t = time.time() - idle_min * 60
    os.utime(p, (t, t))


def _selftest_artifacts() -> list[str]:
    global _STAT
    fails = []
    end = lambda txt: [{"type": "assistant", "message": {"stop_reason": "end_turn", "content": [{"type": "text", "text": txt}]}}]
    with tempfile.TemporaryDirectory() as d:
        ok, empty, gone, cloud = (Path(d) / n for n in ("done.md", "empty.md", "absent.md", "cloud.md"))
        ok.write_text("content")
        empty.write_text("")
        cloud.write_text("x" * 50)
        cases = [
            ("kept", f"Done. I saved it to {ok}.", FINISHED),
            ("missing", f"Done. I saved it to {gone}.", MISSING),
            ("zero bytes", f"Done. I wrote `{empty}`.", MISSING),
            ("placeholder", f"Done. I saved it to {cloud}.", NV),
            ("only read", f"I read {gone} and the summary was clear. I saved it to {ok}.", FINISHED),
            ("read, no promise", f"I read the file {gone} in full.", FINISHED),
            ("relative", "I saved it to docs/out.md.", NV),
            ("no path", "Done, all fine.", FINISHED),
            ("missing beats placeholder", f"I saved {cloud} and {gone}.", MISSING),
        ]
        real = os.stat

        def fake(p):  # only cloud.md pretends to be a placeholder: size > 0 and no blocks
            st = real(p)
            if str(p) == str(cloud):
                class S:
                    st_size, st_blocks, st_flags = st.st_size, 0, DATALESS
                return S
            return st
        _STAT = fake
        try:
            for name, txt, want in cases:
                got, _ = judge_artifacts(end(txt))
                if got != want:
                    fails.append(f"artifact/{name}: {got} != {want}")
        finally:
            _STAT = real
    if exit_code([{"state": MISSING}]) != 1 or exit_code([{"state": FINISHED}]) != 0:
        fails.append("artifact: wrong rc")
    return fails


def selftest() -> int:
    A = lambda stop=None, blocks=None: {"type": "assistant", "message": {"stop_reason": stop, "content": blocks or [{"type": "text", "text": "ok"}]}}
    wait = A(None, [{"type": "tool_use", "name": "Bash", "input": {"command": "sleep 1; ls /srv/work/render/out.mp4"}},
                    {"type": "text", "text": "waiting for the render monitor"}])
    fails = []
    with tempfile.TemporaryDirectory() as d:
        sub = Path(d) / "s" / "subagents"
        sub.mkdir(parents=True)
        _write(sub / "agent-stopped.jsonl", [wait, {"type": "user"}], 40)
        _write(sub / "agent-recent.jsonl", [wait, {"type": "user"}], 1)
        _write(sub / "agent-done.jsonl", [A("end_turn"), {"attachment": {"hookEvent": "SubagentStop"}}], 90)
        _write(sub / "agent-done2.jsonl", [A("end_turn")], 90)
        (sub / "agent-bad.jsonl").write_text("{not json\n", encoding="utf-8")
        (sub / "agent-empty.jsonl").write_text("", encoding="utf-8")
        _write(sub / "agent-ffmpeg.jsonl", [wait, {"type": "user"}], 40)
        quiet = [{"pid": 1, "cpu": 0.0, "cmd": "/x/chrome-headless-shell --headless"}]
        rs = {r["agent"]: r for r in scan(Path(d) / "s", 10, ps=quiet)}
        want = {"stopped": STOPPED, "recent": RUNNING, "done": FINISHED, "done2": FINISHED, "bad": NV, "empty": NV, "ffmpeg": STOPPED}
        for k, v in want.items():
            if rs[k]["state"] != v:
                fails.append(f"{k}: {rs[k]['state']} != {v}")
        if not rs["bad"]["reason"]:
            fails.append("NOT_VERIFIED without a reason")
        busy = [{"pid": 2, "cpu": 80.0, "cmd": "ffmpeg -i a.mp4 b.mp4"}]
        r2 = {r["agent"]: r for r in scan(Path(d) / "s", 10, ps=busy)}
        if r2["ffmpeg"]["state"] != RUNNING or r2["done"]["state"] != FINISHED:
            fails.append("ffmpeg with CPU should keep an unfinished agent RUNNING")
        py = [{"pid": 3, "cpu": 50.0, "cmd": "python3 /srv/work/render/gen.py"}]
        if evaluate(sub / "agent-stopped.jsonl", time.time(), 10, py)["state"] != RUNNING:
            fails.append("python on the agent's path with CPU should be RUNNING")
        if evaluate(sub / "agent-stopped.jsonl", time.time(), 10, None)["state"] != NV:
            fails.append("no process list and an idle transcript should be NOT_VERIFIED")
        if exit_code(list(rs.values())) != 1 or exit_code([rs["done"]]) != 0 or exit_code([rs["bad"]]) != 3 or exit_code([]) != 3:
            fails.append("wrong rc")
    fails += _selftest_artifacts()
    for f in fails:
        print("FAILED:", f)
    print("selftest:", "OK" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


def _safe_stdio() -> None:
    """A Windows console or pipe may use cp1252/cp437: an unencodable character must print as '?', not crash."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _safe_stdio()
    ap = argparse.ArgumentParser(description="Find background subagents that stopped without finishing.")
    ap.add_argument("--session", default="current", help="id prefix, folder, or 'current' (newest session of this directory)")
    ap.add_argument("--min", type=int, default=10, help="minutes without growth to count as stopped")
    ap.add_argument("--root", default=str(ROOT), help="where the sessions live (default ~/.claude/projects)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.min < 1:
        ap.error("--min must be at least 1")
    try:
        rs = scan(find_session(a.session, Path(a.root)), a.min)
    except (FileNotFoundError, OSError) as ex:
        print(f"NOT_VERIFIED: {ex}", file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps(rs, indent=2))
    else:
        show(rs)
    return exit_code(rs)


if __name__ == "__main__":
    sys.exit(main())
