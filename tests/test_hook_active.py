"""The versioned hook only protects if it is ACTIVE.

`core.hooksPath` is LOCAL git config: in a new clone the file `.githooks/pre-commit` exists on
disk and does NOT fire. This test is the alarm for that case: it stays red until someone runs
`sh install.sh`, and goes red again if someone runs `git config --unset core.hooksPath`.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_hookspath_points_to_githooks():
    r = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=ROOT, capture_output=True, text=True)
    assert r.stdout.strip() == ".githooks", (
        f"core.hooksPath = {r.stdout.strip()!r}, expected '.githooks'. The hook exists on disk but does NOT fire. "
        "Run: sh install.sh")


def test_the_hook_exists_and_is_executable():
    hook = ROOT / ".githooks" / "pre-commit"
    assert hook.is_file() and os.access(hook, os.X_OK)


def test_the_hook_calls_the_ring_and_the_leak_scanner():
    text = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "core/ring.py" in text and "--gate --stage" in text
    assert "core/leak.py" in text and "--staged" in text
