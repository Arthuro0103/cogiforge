"""Tests for tests/mutate.py: an interrupted run must not leave the suite (or its children) running."""
import os
import shutil
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


@pytest.fixture
def repo(tmp_path):
    """A real git repo whose tests/mutate.py is a copy of the real one (so its ROOT is the temp repo)."""
    def git(*a):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *a], cwd=tmp_path,
                              check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q", "-b", "main")
    (tmp_path / "tests").mkdir()
    shutil.copy(HERE / "mutate.py", tmp_path / "tests" / "mutate.py")
    for f in ("README.md", "docs/a.md", "assets/x.png", "core/gate.py", "tests/conftest.py", "tests/test_x.py",
              "CLAUDE.md", "AGENTS.md"):
        (tmp_path / f).parent.mkdir(exist_ok=True)
        (tmp_path / f).write_text("# a\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")

    class R:
        path = tmp_path
        base = git("rev-parse", "HEAD")

        def commit(self, files=None, rename=None, delete=()):
            for f, body in (files or {}).items():
                (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
                (tmp_path / f).write_text(body)
            if rename:
                git("mv", *rename)
            for f in delete:
                git("rm", "-q", f)
            git("add", "-A")
            git("commit", "-q", "-m", "change")

        def decide(self, ref):
            import importlib.util
            spec = importlib.util.spec_from_file_location("mutate_in_repo", tmp_path / "tests" / "mutate.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.skip_decision(ref)

        def cli(self, *args):
            r = subprocess.run([sys.executable, str(tmp_path / "tests" / "mutate.py"), *args], capture_output=True,
                               text=True, cwd=tmp_path)
            return r.returncode, r.stdout
    return R()


def test_only_docs_changed_skips_the_mutation(repo):
    repo.commit({"README.md": "b", "docs/a.md": "b", "assets/x.png": "b", "docs/new/deep.md": "b"})
    skip, msg = repo.decide(repo.base)
    assert skip and "only docs changed (4 files)" in msg
    rc, out = repo.cli("--changed-since", repo.base)
    assert rc == 0 and "nothing to mutate since" in out and "only docs changed" in out


@pytest.mark.parametrize("files", [
    {"tests/conftest.py": "b"},          # the suites import it: it once let a green CI skip 2 live mutants
    {"core/gate.py": "b"},               # a module another piece imports
    {"CLAUDE.md": "b"}, {"AGENTS.md": "b"}, {"vault/n.md": "b"}, {"demo/n.md": "b"}, {".github/w.yml": "b"},
    {"README.md": "b", "core/gate.py": "b"},   # one relevant file among docs
    {"docs/../core/gate.py": "b"},
    {"README.md.bak": "b"}, {"docsx/a.md": "b"},   # look-alikes are not docs
])
def test_any_non_doc_change_mutates_everything(repo, files):
    repo.commit(files)
    skip, msg = repo.decide(repo.base)
    assert not skip and "every piece is mutated" in msg
    rc, out = repo.cli("--changed-since", repo.base, "--dry")
    assert "nothing to mutate" not in out        # the real entry point agrees: it goes on to the pieces


def test_renaming_a_test_file_mutates_everything_even_into_docs(repo):
    repo.commit(rename=("tests/test_x.py", "docs/test_x.md"))      # the old path is on the list of changes too
    assert not repo.decide(repo.base)[0]


def test_deleting_a_code_file_mutates_everything(repo):
    repo.commit(delete=("core/gate.py",))
    assert not repo.decide(repo.base)[0]


def test_the_runner_itself_changing_mutates_everything(repo):
    repo.commit({"tests/mutate.py": (repo.path / "tests" / "mutate.py").read_text() + "\n# changed\n"})
    assert not repo.decide(repo.base)[0]


def test_unknown_or_unusable_refs_mutate_everything(repo):
    for ref in ("0" * 40, "no-such-ref-xyz", "", None):
        skip, msg = repo.decide(ref)
        assert not skip and "cannot tell" in msg


def test_nothing_changed_since_head_is_nothing_to_mutate(repo):
    skip, msg = repo.decide("HEAD")
    assert skip and "no file changed" in msg
    assert repo.cli("--changed-since", "HEAD")[0] == 0


def test_the_diff_looks_from_the_ref_to_head_not_the_other_way(repo):
    """`HEAD...REF` would see nothing (or the other side) when REF is an ancestor: a code change must still show."""
    repo.commit({"core/gate.py": "b"})
    mod_files = None
    import importlib.util
    spec = importlib.util.spec_from_file_location("mutate_dir", repo.path / "tests" / "mutate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod_files = mod.changed_files(repo.base)
    assert mod_files == ["core/gate.py"]          # not [] (inverted range) and not None


def test_a_name_with_odd_characters_is_listed_whole(repo):
    odd_a, odd_b = "docs/na\u00efve file.md", "core/caf\u00e9.py"      # non-ASCII + a space, git must not quote them
    repo.commit({odd_a: "b", odd_b: "b"})
    import importlib.util
    spec = importlib.util.spec_from_file_location("mutate_odd", repo.path / "tests" / "mutate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert sorted(mod.changed_files(repo.base)) == sorted([odd_a, odd_b])


def test_only_irrelevant_is_false_for_an_empty_list_and_exact_for_names():
    mod = _mod()
    assert not mod.only_irrelevant([])
    assert mod.only_irrelevant(["README.md", "LEIA-ME.md", "WHY.md", "TUTORIAL.md", "LICENSE", "preview.html",
                                "docs/x/y.md", "assets/a.png"])
    for bad in ("CLAUDE.md", "AGENTS.md", "vault/a.md", "demo/a.md", "tests/a.py", ".github/a.yml", "core/a.py",
                "docs", "assets", "xdocs/a.md", "sub/README.md"):
        assert not mod.only_irrelevant([bad]), bad


def test_a_piece_whose_file_is_missing_is_rc_2_not_skipped(repo):
    rc, out = repo.cli("leak")            # the temp repo has no core/leak.py
    assert rc == 2 and "does not exist" in out
    rc, out = repo.cli("leak", "--dry")
    assert rc == 2 and "does not exist" in out


def test_a_shard_with_no_mutant_says_not_verified(repo):
    (repo.path / "core").mkdir(exist_ok=True)
    # a piece with exactly 1 mutant, in a temp repo: shard 2/2 owns nothing
    (repo.path / "core" / "one.py").write_text("X = 1\n")
    (repo.path / "tests" / "test_one.py").write_text("def test_ok():\n    assert True\n")
    runner = (repo.path / "tests" / "mutate.py").read_text()
    runner = runner.replace("PIECES = {", 'PIECES = {\n    "one": dict(file="core/one.py", suite=["tests/test_one.py"], '
                            'texts=[("x", "X = 1", "X = 2")]),', 1)
    (repo.path / "tests" / "mutate.py").write_text(runner)
    rc, out = repo.cli("one", "--shard", "2/2")
    assert rc == 0 and "NOT_VERIFIED: this shard had no mutant to run" in out
    rc, out = repo.cli("one", "--shard", "1/2")
    assert rc == 1 and "SURVIVED" in out and "NOT_VERIFIED" not in out, out   # test is always green: the mutant lives
