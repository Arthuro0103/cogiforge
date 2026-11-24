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


def world(tmp_path, items, profile="The user likes jasmine tea.\n", decisions="", archive=None, rules="", bank=True):
    v = tmp_path / "vault"
    put(v / "memory" / "profile.md", profile)
    put(v / "memory" / "decisions.md", decisions)
    if archive is not None:
        put(v / "memory" / "archive" / "decisions.md", archive)
    if rules:
        put(tmp_path / "CLAUDE.md", rules)
    if bank:
        put(v / "memory" / "recall.json", items if isinstance(items, str) else json.dumps({"items": items}))
    return v


def recall(tmp_path, *args):
    v = tmp_path / "vault"
    return subprocess.run([sys.executable, RECALL, "--vault", str(v), "--root", str(tmp_path), *args],
                          capture_output=True, text=True, timeout=120)


def fake_model(tmp_path, answers: str) -> str:
    script = put(tmp_path / "fake_model.py", f"import sys\nsys.stdin.read()\nprint({answers!r})\n")
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
