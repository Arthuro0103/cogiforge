"""Paired tests for flags.py: it lists flags WITHOUT running the script, and never pretends to be complete.

The central test plants a script whose first line writes a sentinel file. If flags.py imported or ran the
target, the sentinel would appear. A twin test shows the naive way (importing) does create it.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

FLAGS = str(Path(__file__).with_name("flags.py"))

ARGPARSE = "import argparse\np = argparse.ArgumentParser()\np.add_argument('--target')\n"


def run(*args):
    return subprocess.run([sys.executable, FLAGS, *map(str, args)], capture_output=True, text=True, timeout=60)


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def sentinel_script(tmp_path):
    sentinel = tmp_path / "SENTINEL.txt"
    script = put(tmp_path / "tools" / "risky.py", f"open({str(sentinel)!r}, 'w').write('x')\n" + ARGPARSE)
    return sentinel, script


def test_the_target_script_is_never_executed(tmp_path):
    sentinel, script = sentinel_script(tmp_path)
    r = run(script)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--target" in r.stdout
    assert not sentinel.exists(), "flags.py EXECUTED the target script"


def test_tables_do_not_execute_either(tmp_path):
    sentinel, _ = sentinel_script(tmp_path)
    md = put(tmp_path / "CLAUDE.md", "`python3 tools/risky.py --target X`\n")
    assert run("--tables", md).returncode == 0
    assert not sentinel.exists()


def test_the_twin_importing_the_module_does_create_the_sentinel(tmp_path):
    sentinel, script = sentinel_script(tmp_path)
    spec = importlib.util.spec_from_file_location("risky", script)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    assert sentinel.exists()


def test_a_cited_flag_that_exists_is_ok(tmp_path):
    put(tmp_path / "tools" / "x.py", ARGPARSE)
    md = put(tmp_path / "CLAUDE.md", "| What | Command |\n|---|---|\n| go | `python3 tools/x.py --target X` |\n")
    r = run("--tables", md)
    assert r.returncode == 0, r.stdout
    assert "1 OK" in r.stdout and "0 STALE" in r.stdout


def test_a_cited_flag_that_does_not_exist_is_stale(tmp_path):
    put(tmp_path / "tools" / "x.py", ARGPARSE)
    md = put(tmp_path / "CLAUDE.md", "intro\n| go | `python3 tools/x.py --missing` |\n")
    r = run("--tables", md)
    assert r.returncode == 1, r.stdout
    assert "STALE" in r.stdout and "CLAUDE.md:2" in r.stdout and "--missing" in r.stdout


def test_the_second_flag_after_a_dot_separator_is_checked_too(tmp_path):
    put(tmp_path / "tools" / "x.py", ARGPARSE)
    md = put(tmp_path / "CLAUDE.md", "| go | `python3 tools/x.py --target A` . `python3 tools/x.py --ghost` |\n")
    assert run("--tables", md).returncode == 1


def test_brackets_around_an_optional_flag_are_ignored(tmp_path):
    put(tmp_path / "tools" / "x.py", ARGPARSE)
    md = put(tmp_path / "CLAUDE.md", "| go | `python3 tools/x.py <name> [--target]` |\n")
    assert run("--tables", md).returncode == 0


def test_an_unambiguous_argparse_abbreviation_is_ok_but_an_ambiguous_one_is_stale(tmp_path):
    put(tmp_path / "tools" / "x.py",
        "import argparse\np = argparse.ArgumentParser()\np.add_argument('--target')\np.add_argument('--tag')\n")
    assert run("--tables", put(tmp_path / "a.md", "`python3 tools/x.py --tar`\n")).returncode == 0
    assert run("--tables", put(tmp_path / "b.md", "`python3 tools/x.py --ta`\n")).returncode == 1


def test_a_dead_script_path_is_not_verified_not_stale(tmp_path):
    r = run("--tables", put(tmp_path / "CLAUDE.md", "`python3 tools/gone.py --x`\n"))
    assert r.returncode == 3
    assert "NOT_VERIFIED" in r.stdout and "dead path" in r.stdout


def test_a_table_with_no_command_is_not_verified_never_ok(tmp_path):
    r = run("--tables", put(tmp_path / "CLAUDE.md", "# Nothing here\n\nNo commands at all.\n"))
    assert r.returncode == 3
    assert "NOT_VERIFIED" in r.stdout and "not OK" in r.stdout


def test_a_script_cited_without_any_flag_verifies_nothing(tmp_path):
    put(tmp_path / "tools" / "x.py", ARGPARSE)
    r = run("--tables", put(tmp_path / "CLAUDE.md", "`python3 tools/x.py`\n"))
    assert r.returncode == 3


def test_a_missing_doc_is_not_verified(tmp_path):
    assert run("--tables", tmp_path / "nope.md").returncode == 3


def test_a_dynamic_parser_is_not_verified_and_says_the_list_is_incomplete(tmp_path):
    script = put(tmp_path / "d.py", ARGPARSE + "for f in ['--a', '--b']:\n    p.add_argument(f)\n")
    r = run(script)
    assert r.returncode == 3
    assert "NOT_VERIFIED" in r.stdout and "INCOMPLETE" in r.stdout and "L5" in r.stdout and "--target" in r.stdout


def test_a_flag_only_a_dynamic_snippet_could_declare_is_not_stale(tmp_path):
    put(tmp_path / "tools" / "d.py", "import argparse\np = argparse.ArgumentParser()\nfor f in ['--a']:\n    p.add_argument(f)\n")
    r = run("--tables", put(tmp_path / "CLAUDE.md", "`python3 tools/d.py --a`\n"))
    assert r.returncode == 3 and "1 STALE" not in r.stdout


def test_starred_and_fstring_names_are_dynamic(tmp_path):
    script = put(tmp_path / "e.py", "import argparse\np = argparse.ArgumentParser()\nn = ['--a']\np.add_argument(*n)\np.add_argument(f'--{1}x')\n")
    r = run(script)
    assert r.returncode == 3 and "L4" in r.stdout and "L5" in r.stdout


def test_a_script_with_no_parser_is_nothing_to_measure(tmp_path):
    r = run(put(tmp_path / "n.py", "print('hi')\n"))
    assert r.returncode == 3
    assert "nothing_to_measure" in r.stdout and "NOT_VERIFIED" in r.stdout


def test_sys_argv_flags_are_listed_with_their_origin(tmp_path):
    script = put(tmp_path / "s.py", (
        "import sys\nif '--only' in sys.argv:\n    pass\nif sys.argv[1] == '--one':\n    pass\n"
        "args = sys.argv[1:]\nif any(a.startswith('--pref') for a in args):\n    pass\n"))
    r = run(script)
    assert r.returncode == 0, r.stdout
    assert all(f in r.stdout for f in ("--only", "--one", "--pref"))
    assert "sys.argv" in r.stdout and "argparse" not in r.stdout


def test_a_computed_startswith_prefix_is_incomplete(tmp_path):
    script = put(tmp_path / "p.py", "import sys\nPRE = '--x'\nif '--known' in sys.argv:\n    pass\nfor a in sys.argv[1:]:\n    if a.startswith(PRE + 'y'):\n        pass\n")
    r = run(script)
    assert r.returncode == 3 and "INCOMPLETE" in r.stdout


def test_add_help_false_does_not_invent_help(tmp_path):
    r = run(put(tmp_path / "h.py", "import argparse\np = argparse.ArgumentParser(add_help=False)\np.add_argument('-q', '--quiet')\n"))
    assert "--quiet" in r.stdout and "--help" not in r.stdout


def test_an_unparseable_script_is_not_verified(tmp_path):
    assert run(put(tmp_path / "bad.py", "def (:\n")).returncode == 3


def test_selftest_passes():
    r = run("--selftest")
    assert r.returncode == 0 and "OK" in r.stdout


def test_the_real_repo_docs_match_the_real_flags():
    r = run("--tables")
    assert r.returncode in (0, 3), r.stdout  # never STALE; 3 only if a script is dynamic
    assert "STALE:" not in r.stdout


def test_every_flag_in_one_command_is_checked_not_only_the_first(tmp_path):
    put(tmp_path / "tools" / "x.py", ARGPARSE)
    r = run("--tables", put(tmp_path / "CLAUDE.md", "| go | `python3 tools/x.py --target A --ghost` |\n"))
    assert r.returncode == 1 and "--ghost" in r.stdout
