"""Paired tests for agents_watch.py: the agent that said "waiting for the render" and stopped must come out STOPPED;
one that finished or is still growing must not."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agents_watch as w  # noqa: E402

TOOL = str(Path(__file__).with_name("agents_watch.py"))
WAIT = {"type": "assistant", "message": {"stop_reason": None, "content": [
    {"type": "tool_use", "name": "Bash", "input": {"command": "ls /srv/work/render/out.mp4"}},
    {"type": "text", "text": "waiting for the render monitor"}]}}
END = {"type": "assistant", "message": {"stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}]}}


def mk(tmp, name, entries, idle_min):
    d = tmp / "subagents"
    d.mkdir(exist_ok=True)
    p = d / f"agent-{name}.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    t = time.time() - idle_min * 60
    os.utime(p, (t, t))
    return p


def states(tmp, ps=()):
    return {r["agent"]: r for r in w.scan(tmp, 10, ps=list(ps))}


def test_stopped_recent_finished_unreadable(tmp_path):
    mk(tmp_path, "stopped", [WAIT, {"type": "user"}], 40)
    mk(tmp_path, "recent", [WAIT, {"type": "user"}], 1)
    mk(tmp_path, "done", [END], 90)
    (tmp_path / "subagents" / "agent-bad.jsonl").write_text("", encoding="utf-8")
    r = states(tmp_path)
    assert r["stopped"]["state"] == w.STOPPED
    assert r["recent"]["state"] == w.RUNNING
    assert r["done"]["state"] == w.FINISHED
    assert r["bad"]["state"] == w.NV and r["bad"]["reason"]
    assert w.exit_code(list(r.values())) == 1


def test_a_process_with_cpu_saves_it_and_an_idle_one_does_not(tmp_path):
    mk(tmp_path, "a", [WAIT, {"type": "user"}], 40)
    idle = [{"pid": 1, "cpu": 0.0, "cmd": "chrome-headless-shell x"}]
    busy = [{"pid": 2, "cpu": 90.0, "cmd": "ffmpeg -i a b"}]
    assert states(tmp_path, idle)["a"]["state"] == w.STOPPED
    assert states(tmp_path, busy)["a"]["state"] == w.RUNNING


def test_no_process_list_is_not_verified_never_stopped_or_ok(tmp_path):
    p = mk(tmp_path, "a", [WAIT, {"type": "user"}], 40)
    r = w.evaluate(p, time.time(), 10, None)
    assert r["state"] == w.NV and r["reason"]


def test_missing_promised_file_is_an_alarm(tmp_path):
    gone = tmp_path / "absent.md"
    done = {"type": "assistant", "message": {"stop_reason": "end_turn", "content": [{"type": "text", "text": f"Done. I saved it to {gone}."}]}}
    mk(tmp_path, "x", [done], 90)
    r = states(tmp_path)
    assert r["x"]["state"] == w.MISSING and w.exit_code(list(r.values())) == 1


def test_exit_codes(tmp_path):
    assert w.exit_code([]) == 3
    mk(tmp_path, "done", [END], 90)
    assert w.exit_code(list(states(tmp_path).values())) == 0


def test_session_not_found_is_not_verified(tmp_path):
    r = subprocess.run([sys.executable, TOOL, "--session", "nope", "--root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stderr


def test_cli_json_over_a_session_folder(tmp_path):
    mk(tmp_path, "done", [END], 90)
    r = subprocess.run([sys.executable, TOOL, "--session", str(tmp_path), "--json"], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)[0]["state"] == w.FINISHED


def test_bad_min_is_a_usage_error():
    assert subprocess.run([sys.executable, TOOL, "--min", "0"], capture_output=True, text=True).returncode == 2


def test_the_selftest_passes():
    assert w.selftest() == 0


def test_a_subagent_stop_event_alone_means_finished(tmp_path):
    mk(tmp_path, "s", [WAIT, {"attachment": {"hookEvent": "SubagentStop"}}], 90)
    assert states(tmp_path)["s"]["state"] == w.FINISHED
