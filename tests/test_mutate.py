"""Tests for tests/mutate.py: an interrupted run must not leave the suite (or its children) running."""
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for(path, secs=30):
    end = time.time() + secs
    while time.time() < end:
        if path.exists() and path.read_text().strip():
            return True
        time.sleep(0.1)
    return False


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="process groups do not exist on Windows")
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_a_signal_kills_the_suite_and_its_children(tmp_path, sig):
    pidfile = tmp_path / "child.pid"
    suite = tmp_path / "test_slow.py"
    suite.write_text(textwrap.dedent(f"""
        import subprocess, sys, time
        def test_slow():
            child = subprocess.Popen(["sleep", "300"])
            open({str(pidfile)!r}, "w").write(str(child.pid))
            time.sleep(300)
    """))
    harness = tmp_path / "harness.py"
    harness.write_text(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(HERE)!r})
        import mutate
        mutate.install_handlers()
        mutate.run_suite([{str(suite)!r}])
    """))
    h = subprocess.Popen([sys.executable, str(harness)], stdin=subprocess.DEVNULL)
    try:
        assert wait_for(pidfile), "the suite never started its child"
        child = int(pidfile.read_text())
        assert alive(child)
        h.send_signal(sig)
        h.wait(timeout=30)
        end = time.time() + 10
        while alive(child) and time.time() < end:
            time.sleep(0.1)
        assert not alive(child), "the child of the suite was left running"
    finally:
        h.kill()
        if pidfile.exists() and pidfile.read_text().strip():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_a_mutant_gets_three_times_the_baseline_and_never_less_than_the_floor():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mutate_mod", Path(__file__).resolve().parent / "mutate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.mutant_limit(10) == mod.SUITE_TIMEOUT          # a fast suite keeps the floor
    assert mod.mutant_limit(362) == 3 * 362                   # the hook suite of 2026-11-24 (362 s) gets 1086 s
    assert mod.BASELINE_TIMEOUT > 3 * mod.SUITE_TIMEOUT        # the unmutated run is never cut at the mutant floor
