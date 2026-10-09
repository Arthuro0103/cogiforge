"""Smoke tests for bench.py: it runs every tool on a small synthetic vault and never reports a tool it could not run as fast."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

BENCH = str(Path(__file__).with_name("bench.py"))


def test_measure_returns_time_memory_and_the_exit_code(tmp_path):
    r = bench.median_run([sys.executable, "-c", "x = bytearray(30_000_000)"], tmp_path, 2)
    assert r["rc"] == 0 and r["s"] > 0 and r["mb"] > 25 and 0 < r["cpu"] <= r["s"] + 0.5


def test_a_failing_tool_keeps_its_exit_code(tmp_path):
    assert bench.median_run([sys.executable, "-c", "raise SystemExit(3)"], tmp_path, 1)["rc"] == 3


def test_the_table_marks_a_missing_tool_and_a_failing_one(tmp_path):
    data = {100: {"gate": {"rc": 0, "s": 1.234, "cpu": 0.9, "mb": 20.2}, "usage": {"missing": True}, "ring": {"rc": 1, "s": 0.5, "cpu": 0.4, "mb": 9.0}}}
    t = bench.table([100], data)
    assert "| gate | 1.23 s (0.90 cpu), 20 MB |" in t and "| usage | missing |" in t and "(rc 1)" in t


def test_a_small_end_to_end_run_measures_every_tool_and_all_exit_clean(tmp_path):
    r = subprocess.run([sys.executable, BENCH, "--sizes", "120", "--runs", "1", "--out", str(tmp_path / "t.md")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    out = (tmp_path / "t.md").read_text()
    for tool in ("gate", "ring", "hub", "search", "cite", "import", "leak", "usage", "context", "pre-commit (cold)", "pre-commit (warm)"):
        assert f"| {tool} |" in out, tool
    assert "missing" not in out and "(rc" not in out, out
    assert out.startswith("Machine: ") and "Median of 1 runs" in out
