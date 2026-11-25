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
@pytest.mark.parametrize("sig", [getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGHUP") if hasattr(signal, n)])
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
                os.kill(int(pidfile.read_text()), getattr(signal, "SIGKILL", signal.SIGTERM))
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


def test_mutate_imports_without_sighup(monkeypatch):
    """Windows has no signal.SIGHUP: importing mutate.py must not touch it."""
    import importlib.util
    monkeypatch.delattr(signal, "SIGHUP", raising=False)
    assert not hasattr(signal, "SIGHUP")
    spec = importlib.util.spec_from_file_location("mutate_nohup", Path(__file__).parent / "mutate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


def _mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mutate_sel", HERE / "mutate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("n", [1, 3, 8])
def test_the_shards_of_a_piece_partition_its_mutants(n):
    mod = _mod()
    items = [f"m{k}" for k in range(20)]
    parts = [mod.select_shard(items, (i, n)) for i in range(1, n + 1)]
    flat = [x for p in parts for x in p]
    assert sorted(flat) == sorted(items) and len(flat) == len(set(flat))
    assert all(mod.shard_of(items.index(x), n) == i for i, p in enumerate(parts, 1) for x in p)


def test_no_shard_keeps_every_mutant_and_a_bad_shard_is_refused():
    mod = _mod()
    assert mod.select_shard(["a", "b"], None) == ["a", "b"]
    assert mod.parse_shard("3/8") == (3, 8)
    for bad in ("0/8", "9/8", "x", "1", "1/0", ""):
        with pytest.raises(ValueError):
            mod.parse_shard(bad)
    r = subprocess.run([sys.executable, str(HERE / "mutate.py"), "--shard", "9/8"], capture_output=True, text=True)
    assert r.returncode == 2


def test_the_diff_selects_the_pieces_by_file_suite_or_changed_entry():
    mod = _mod()
    new = {"a": dict(file="core/a.py", suite=["tests/test_a.py"], texts=[("x", "1", "2")]),
           "b": dict(file="core/b.py", suite=["tests/test_b.py", "tests/shared.py"], texts=[]),
           "c": dict(file="core/c.py", suite=["tests/test_c.py"], texts=[])}
    same = {k: dict(v) for k, v in new.items()}
    assert mod.affected_pieces([], same, new) == []
    assert mod.affected_pieces(["README.md"], same, new) == []
    assert mod.affected_pieces(["core/a.py"], same, new) == ["a"]
    assert mod.affected_pieces(["tests/shared.py"], same, new) == ["b"]
    assert mod.affected_pieces(["tests/test_c.py", "core/a.py"], same, new) == ["a", "c"]
    old = {k: dict(v) for k, v in new.items()}
    old["c"] = dict(old["c"], texts=[("y", "1", "2")])
    assert mod.affected_pieces([], old, new) == ["c"]            # entry changed, no file changed
    del old["b"]
    assert mod.affected_pieces([], old, new) == ["b", "c"]        # a new piece counts
    assert mod.affected_pieces([], None, new) == ["a", "b", "c"]  # old PIECES unreadable: all


def test_an_unknown_ref_means_every_piece_and_head_means_none():
    mod = _mod()
    for ref in ("0" * 40, "no-such-ref-xyz"):
        assert mod.changed_selection(ref) == (list(mod.PIECES), False)
    assert mod.changed_selection("HEAD") == ([], False)


def test_pieces_literal_is_read_from_an_old_source():
    mod = _mod()
    old = (HERE / "mutate.py").read_text(encoding="utf-8")
    assert mod.load_pieces(old) == mod.PIECES
    assert mod.load_pieces("nothing here") is None
