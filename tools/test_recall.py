"""Paired tests for recall.py: a fact is loaded, archived WITH a pointer, or missing; and the model run is graded honestly."""
import json
import subprocess
import sys
from pathlib import Path

RECALL = str(Path(__file__).with_name("recall.py"))

POINTER = "- [[memory/archive/decisions|3 older entries, moved word for word on 2026-10-01]]\n"
POS = {"id": "pos", "type": "positive-control", "question": "Favorite tea?", "accept": ["jasmine"]}
NEG = {"id": "neg", "type": "negative-control", "question": "Account number?"}
REC = {"id": "rec", "type": "recall", "question": "Start time?", "accept": ["6 am"]}


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def world(tmp_path, items, profile="The user likes jasmine tea.\n", decisions="", archive=None, rules="", bank=True,
          agents="", vault_rules="", patterns=None, patterns_archive=None, extra=None):
    v = tmp_path / "vault"
    put(v / "memory" / "profile.md", profile)
    put(v / "memory" / "decisions.md", decisions)
    if archive is not None:
        put(v / "memory" / "archive" / "decisions.md", archive)
    if rules:
        put(tmp_path / "CLAUDE.md", rules)
    if agents:
        put(tmp_path / "AGENTS.md", agents)
    if vault_rules:
        put(v / "CLAUDE.md", vault_rules)
    if patterns is not None:
        put(v / "memory" / "patterns.md", patterns)
    if patterns_archive is not None:
        put(v / "memory" / "archive" / "patterns.md", patterns_archive)
    for rel, text in (extra or {}).items():
        put(v / rel, text)
    if bank:
        put(v / "memory" / "recall.json", items if isinstance(items, str) else json.dumps({"items": items}))
    return v


def recall(tmp_path, *args):
    v = tmp_path / "vault"
    return subprocess.run([sys.executable, RECALL, "--vault", str(v), "--root", str(tmp_path), *args],
                          capture_output=True, text=True, timeout=120)


def fake_model(tmp_path, answers: str, code: int = 0) -> str:
    script = put(tmp_path / "fake_model.py", f"import sys\nsys.stdin.read()\nprint({answers!r})\nsys.exit({code})\n")
    return f"{sys.executable} {script}"


# ------------------------------------------------------------------ the bank

def test_invalid_banks_are_refused_with_rc_2(tmp_path):
    cases = {
        "invalid type": [POS, {**REC, "type": "guess"}],
        "repeated id": [POS, REC, dict(REC)],
        "no question": [POS, {k: v for k, v in REC.items() if k != "question"}],
        "no accept": [POS, {k: v for k, v in REC.items() if k != "accept"}],
        "empty accept": [POS, {**REC, "accept": []}],
        "positive without accept": [{k: v for k, v in POS.items() if k != "accept"}, REC],
        "all is not a boolean": [POS, {**REC, "all": "yes"}],
    }
    for name, items in cases.items():
        r = recall(world(tmp_path, items).parent)
        assert r.returncode == 2, (name, r.stdout, r.stderr)


def test_broken_json_is_rc_2(tmp_path):
    assert recall(world(tmp_path, "{not json").parent).returncode == 2


def test_missing_bank_is_not_verified_and_says_how_to_create_it(tmp_path):
    world(tmp_path, [], bank=False)
    r = recall(tmp_path)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout and "recall.example.json" in r.stdout


def test_bank_without_recall_or_without_positive_control_is_not_verified(tmp_path):
    assert recall(world(tmp_path, [POS, NEG]).parent).returncode == 3
    assert recall(world(tmp_path, [REC, NEG]).parent).returncode == 3


def test_negative_control_needs_no_accept(tmp_path):
    assert recall(world(tmp_path, [POS, REC, NEG], decisions="- 2026-01-01: starts at 6 am\n").parent).returncode == 0


# ------------------------------------------------------------------ static

def test_a_fact_in_a_loaded_file_is_loaded(tmp_path):
    r = recall(world(tmp_path, [POS, REC], decisions="- 2026-01-01: starts at 6 AM\n").parent)
    assert r.returncode == 0 and "rec" in r.stdout and "loaded" in r.stdout


def test_a_fact_in_the_archive_with_the_pointer_is_archived(tmp_path):
    v = world(tmp_path, [POS, REC], decisions=POINTER, archive="- 2026-01-01: starts at 6 am\n")
    r = recall(v.parent)
    assert r.returncode == 0 and "archived" in r.stdout


def test_a_fact_in_the_archive_without_the_pointer_is_missing(tmp_path):
    v = world(tmp_path, [POS, REC], decisions="no pointer here\n", archive="- 2026-01-01: starts at 6 am\n")
    r = recall(v.parent)
    assert r.returncode == 1 and "MISSING" in r.stdout


def test_a_fact_written_nowhere_is_missing(tmp_path):
    assert recall(world(tmp_path, [POS, REC]).parent).returncode == 1


def test_a_term_inside_a_longer_word_does_not_count(tmp_path):
    item = {**REC, "accept": ["air"]}
    assert recall(world(tmp_path, [POS, item], decisions="- 2026-01-01: pairs well\n").parent).returncode == 1


def test_a_fact_also_in_the_rules_file_is_contaminated(tmp_path):
    v = world(tmp_path, [POS, REC], decisions="- 2026-01-01: starts at 6 am\n", rules="Rule: start at 6 am.\n")
    r = recall(v.parent)
    assert r.returncode == 1 and "contaminated" in r.stdout


def test_all_needs_every_term_any_needs_one(tmp_path):
    only_one = "- 2026-01-01: uses a spreadsheet\n"
    both = "- 2026-01-01: uses a spreadsheet and a calendar app\n"
    item = {**REC, "accept": ["spreadsheet", "calendar app"]}
    assert recall(world(tmp_path, [POS, item], decisions=only_one).parent).returncode == 0
    assert recall(world(tmp_path, [POS, {**item, "all": True}], decisions=only_one).parent).returncode == 1
    assert recall(world(tmp_path, [POS, {**item, "all": True}], decisions=both).parent).returncode == 0


def test_a_positive_control_outside_the_loaded_files_is_a_problem(tmp_path):
    v = world(tmp_path, [POS, REC], profile="nothing\n", decisions=POINTER + "- 2026-01-01: starts at 6 am\n",
              archive="The user likes jasmine tea.\n")
    r = recall(v.parent)
    assert r.returncode == 1 and "pos: MISSING" in r.stdout


def test_a_crossed_ceiling_is_a_budget_problem(tmp_path):
    v = world(tmp_path, [POS, REC], decisions="- 2026-01-01: starts at 6 am\n" + "x" * 40_000)
    r = recall(v.parent)
    assert r.returncode == 1 and "BUDGET" in r.stdout


# ------------------------------------------------------------------ --run

def clean(tmp_path, items):
    return world(tmp_path, items, decisions="- 2026-01-01: starts at 6 am\n")


def test_run_all_right_is_ok(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    cmd = fake_model(tmp_path, "1. Jasmine.\n2. 6 AM\n3. I don't know")
    r = recall(tmp_path, "--run", cmd)
    assert r.returncode == 0 and r.stdout.count("OK:") == 1 and "recall 1/1" in r.stdout


def test_run_a_missed_recall_is_degraded(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. I DON'T KNOW\n3. I dont know"))
    assert r.returncode == 1 and "DEGRADED" in r.stdout and "rec" in r.stdout


def test_run_an_invented_negative_control_is_degraded(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am\n3. 12345-6"))
    assert r.returncode == 1 and "DEGRADED" in r.stdout and "invented ['neg']" in r.stdout


def test_run_a_missed_positive_control_is_not_verified(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. I don't know\n2. I don't know\n3. I don't know"))
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_run_i_dont_know_in_the_middle_does_not_count(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am\n3. 12345, I don't know if it is right"))
    assert r.returncode == 1 and "invented ['neg']" in r.stdout


def test_run_i_dont_know_at_the_start_beats_the_terms(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. I don't know, maybe 6 am\n3. I don't know"))
    assert r.returncode == 1 and "missed ['rec']" in r.stdout


def test_run_is_skipped_when_the_static_check_fails(tmp_path):
    world(tmp_path, [POS, REC])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am"))
    assert r.returncode == 1 and "skipped" in r.stdout


def test_run_a_failing_command_is_not_verified(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    script = put(tmp_path / "bad.py", "import sys\nsys.exit(4)\n")
    assert recall(tmp_path, "--run", f"{sys.executable} {script}").returncode == 3


def test_log_appends_one_json_line(tmp_path):
    v = clean(tmp_path, [POS, REC, NEG])
    cmd = fake_model(tmp_path, "1. jasmine\n2. 6 am\n3. I don't know")
    recall(tmp_path, "--run", cmd, "--log")
    recall(tmp_path, "--run", cmd, "--log")
    lines = (v / "memory" / "recall-history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["verdict"] == "OK" and json.loads(lines[0])["recall_total"] == 1


# ------------------------------------------------------------------ review of the first version

def test_i_dont_know_must_open_the_answer_not_follow_digits(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am\n3. 12345-6 (I don't know if it is current)"))
    assert r.returncode == 1 and "invented ['neg']" in r.stdout


def test_a_bare_number_before_i_dont_know_makes_it_an_answer(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am\n3. 12345 I don't know if it is current"))
    assert r.returncode == 1 and "invented ['neg']" in r.stdout


def test_starts_unknown_directly():
    import importlib.util
    spec = importlib.util.spec_from_file_location("recall_mod2", RECALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for yes in ("> 2. I don't know", "*I DON'T KNOW*", "_I do not know_", "3) I dont know", "I don\u2019t know"):
        assert mod.starts_unknown(yes), yes
    for no in ("12345 I don't know", "\"I don't know\"", "maybe I don't know", "3. 12345-6 (I don't know)"):
        assert not mod.starts_unknown(no), no


def test_i_dont_know_accepts_markdown_marks_and_the_long_form(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    for third in ("_I don't know_", "> I don't know", "**I do not know**", "I dont know"):
        r = recall(tmp_path, "--run", fake_model(tmp_path, f"1. jasmine\n2. 6 am\n3. {third}"))
        assert r.returncode == 0, (third, r.stdout)


def test_parse_takes_only_the_next_number_and_continues_the_rest():
    import importlib.util
    spec = importlib.util.spec_from_file_location("recall_mod", RECALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.parse_answers("0. noise\n1. first\n1. repeated\n1.5 h more\n2. second\n  tail\n9. out of range\n", 3)
    assert out == ["first 1. repeated 1.5 h more", "second tail 9. out of range", None]
    assert mod.parse_answers("2. jumps ahead\n1. a\n", 2) == ["a", None]
    assert mod.parse_answers("1. a\n2. b\n3. c\n4. extra\n", 3) == ["a", "b", "c 4. extra"]


def test_a_missing_answer_is_not_verified_never_invented(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am"))
    assert r.returncode == 3 and "did not answer item 3" in r.stdout and "invented" not in r.stdout


def test_a_positive_control_only_in_a_rules_file_is_control_not_in_memory(tmp_path):
    v = world(tmp_path, [POS, REC], profile="nothing\n", decisions="- 2026-01-01: starts at 6 am\n", rules="Jasmine rules.\n")
    r = recall(v.parent)
    assert r.returncode == 1 and "CONTROL-NOT-IN-MEMORY" in r.stdout
    v2 = world(tmp_path, [POS, REC], vault_rules="jasmine too\n", decisions="- 2026-01-01: starts at 6 am\n")
    assert "CONTROL-NOT-IN-MEMORY" in recall(v2.parent).stdout


def test_a_positive_control_in_a_team_memory_file_counts_as_memory(tmp_path):
    v = world(tmp_path, [POS, REC], profile="nothing\n", decisions="- 2026-01-01: starts at 6 am\n",
              extra={"people/ana/memory/profile.md": "likes jasmine\n"})
    assert recall(v.parent).returncode == 0


def test_bank_refuses_a_term_echoed_by_the_question_a_short_term_and_a_bad_id(tmp_path):
    cases = {
        "echo": [POS, {**REC, "question": "Does the user start at 6 AM?"}],
        "short": [POS, {**REC, "accept": ["6"]}],
        "two chars": [POS, {**REC, "accept": ["ab"]}],
        "id with a space": [POS, {**REC, "id": "my rec"}],
        "id with a dot": [POS, {**REC, "id": "a.b"}],
        "empty id": [POS, {**REC, "id": ""}],
    }
    for name, items in cases.items():
        r = recall(world(tmp_path, items).parent)
        assert r.returncode == 2, (name, r.stdout, r.stderr)


def test_the_command_runs_in_the_root(tmp_path):
    v = clean(tmp_path, [POS, REC, NEG])
    script = put(tmp_path / "cwd.py", "import os, sys\nsys.stdin.read()\nopen(os.path.join(os.getcwd(), 'cwd.out'), 'w').write('x')\n"
                 "print('1. jasmine\\n2. 6 am\\n3. I do not know')\n")
    r = recall(tmp_path, "--run", f"{sys.executable} {script}")
    assert r.returncode == 0 and (tmp_path / "cwd.out").exists()


def test_output_that_is_not_utf8_is_not_verified_without_a_traceback(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    script = put(tmp_path / "bad.py", "import sys\nsys.stdin.read()\n"
                 "sys.stdout.buffer.write(b\"1. jasmine\\xff\\n2. 6 am\\n3. I do not know\\n\")\n")
    r = recall(tmp_path, "--run", f"{sys.executable} {script}")
    assert r.returncode == 3 and "Traceback" not in r.stderr


def test_an_unclosed_quote_or_an_empty_command_is_rc_2(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    assert recall(tmp_path, "--run", 'python3 "oops').returncode == 2
    assert recall(tmp_path, "--run", "").returncode == 2


def test_a_command_that_prints_right_answers_but_exits_nonzero_is_not_verified(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. 6 am\n3. I don't know", code=4))
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_a_not_verified_run_prints_no_score_and_logs_null(tmp_path):
    v = clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. I don't know\n2. 6 am\n3. I don't know"), "--log")
    assert r.returncode == 3 and "score not valid" in r.stdout and "recall 0" not in r.stdout and "recall 1" not in r.stdout
    line = json.loads((v / "memory" / "recall-history.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert line["verdict"] == "NOT_VERIFIED" and line["recall_ok"] is None


def test_a_timeout_kills_the_grandchild_too(tmp_path):
    import os
    import time
    clean(tmp_path, [POS, REC, NEG])
    pidfile = tmp_path / "grandchild.pid"
    script = put(tmp_path / "hang.py", "import subprocess, sys, time\nsys.stdin.read()\n"
                 f"p = subprocess.Popen(['sleep', '40'])\nopen({str(pidfile)!r}, 'w').write(str(p.pid))\ntime.sleep(40)\n")
    try:
        # the grandchild holds the output pipe: if it is not killed, recall.py waits for it and this call times out
        r = subprocess.run([sys.executable, RECALL, "--vault", str(tmp_path / "vault"), "--root", str(tmp_path), "--run",
                            f"{sys.executable} {script}", "--timeout", "2"], capture_output=True, text=True, timeout=20)
        assert r.returncode == 3 and "TimeoutExpired" in r.stdout
        pid = int(pidfile.read_text())
        for _ in range(30):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("the grandchild survived the timeout")
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), 9)
            except (ProcessLookupError, ValueError):
                pass


def test_a_pointer_with_md_counts_and_one_in_a_comment_or_a_code_block_does_not(tmp_path):
    arch = "- 2026-01-01: starts at 6 am\n"
    ok = world(tmp_path, [POS, REC], decisions="- [[memory/archive/decisions.md|3 older]]\n", archive=arch)
    assert "archived" in recall(ok.parent).stdout
    for hidden in ("<!-- [[memory/archive/decisions|x]] -->\n", "```\n[[memory/archive/decisions|x]]\n```\n",
                   "~~~\n[[memory/archive/decisions|x]]\n~~~\n", "`[[memory/archive/decisions|x]]`\n"):
        v = world(tmp_path, [POS, REC], decisions=hidden, archive=arch)
        r = recall(v.parent)
        assert r.returncode == 1 and "MISSING" in r.stdout, hidden


def test_all_is_judged_on_the_union_of_the_loaded_files(tmp_path):
    item = {**REC, "accept": ["spreadsheet", "calendar app"], "all": True}
    v = world(tmp_path, [POS, item], profile="likes jasmine, uses a spreadsheet\n", decisions="- 2026-01-01: drops the calendar app\n")
    assert recall(v.parent).returncode == 0


def test_run_does_not_ask_archived_items(tmp_path):
    v = world(tmp_path, [POS, REC, {**REC, "id": "old", "accept": ["tuesdays"], "question": "Which day?"}, NEG],
              decisions=POINTER + "- 2026-01-01: starts at 6 am\n", archive="- 2025-01-01: tuesdays\n")
    marker = tmp_path / "prompt.txt"
    script = put(tmp_path / "echo.py", f"import sys\nopen({str(marker)!r}, 'w').write(sys.stdin.read())\n"
                 "print('1. jasmine\\n2. 6 am\\n3. I do not know')\n")
    r = recall(tmp_path, "--run", f"{sys.executable} {script}")
    assert r.returncode == 0 and "archived: not asked" in r.stdout and "old" in r.stdout
    assert "Which day?" not in marker.read_text(encoding="utf-8")


def test_when_every_recall_is_archived_nothing_was_measured(tmp_path):
    world(tmp_path, [POS, REC, NEG], decisions=POINTER, archive="- 2026-01-01: starts at 6 am\n")
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. I don't know"))
    assert r.returncode == 3 and "nothing was measured" in r.stdout


def test_a_missing_vault_is_not_verified(tmp_path):
    bank = put(tmp_path / "bank.json", json.dumps({"items": [POS, REC]}))
    r = subprocess.run([sys.executable, RECALL, "--vault", str(tmp_path / "nope"), "--bank", str(bank)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 3 and "does not exist" in r.stdout


def test_contamination_is_seen_in_agents_md_and_in_the_vault_claude_md(tmp_path):
    for k, kw in enumerate(({"agents": "start at 6 am\n"}, {"vault_rules": "start at 6 am\n"})):
        v = world(tmp_path / str(k), [POS, REC], decisions="- 2026-01-01: starts at 6 am\n", **kw)
        assert "contaminated" in recall(v.parent).stdout, kw


def test_all_three_memory_stems_are_looked_at_in_the_archive(tmp_path):
    base = tmp_path
    for stem in ("profile", "patterns", "decisions"):
        tmp_path = base / stem
        files = {"profile": "The user likes jasmine tea.\n", "patterns": "", "decisions": ""}
        files[stem] = ("- [[memory/archive/%s|older]]\nThe user likes jasmine tea.\n" % stem) if stem == "profile" else "- [[memory/archive/%s|older]]\n" % stem
        v = world(tmp_path, [POS, REC], profile=files["profile"], patterns=files["patterns"], decisions=files["decisions"],
                  patterns_archive="- 2026-01-01: starts at 6 am\n" if stem == "patterns" else None,
                  archive="- 2026-01-01: starts at 6 am\n" if stem == "decisions" else None,
                  extra={"memory/archive/profile.md": "- 2026-01-01: starts at 6 am\n"} if stem == "profile" else None)
        assert "archived" in recall(v.parent).stdout, stem


def test_continuation_lines_belong_to_the_answer_above(tmp_path):
    clean(tmp_path, [POS, REC, NEG])
    r = recall(tmp_path, "--run", fake_model(tmp_path, "1. jasmine\n2. at\n   6 am sharp\n3. I don't know"))
    assert r.returncode == 0
