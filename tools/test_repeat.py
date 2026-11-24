"""Paired tests for repeat.py: a correction that restates an older memory is a repeat; nothing else is."""
import json
import subprocess
import sys
from pathlib import Path

REPEAT = str(Path(__file__).with_name("repeat.py"))

MEMORY = """# Patterns

- 2026-01-01 | "never invent a link to a shop page before you opened it" | chat
- 2026-01-02 | "keep the answers short and direct" | chat
- 2026-03-01 | "always check the dishwasher filter weekly" | chat
"""
OBS = """# Observations

- 2026-02-10: you invented a link to a shop page again, open it before you link it
- 2026-02-20: another invented link to a shop page, I said open it before you link it
- 2026-02-25: the weather report was in celsius and I wanted fahrenheit
- 2026-02-01: dishwasher filter check weekly, forgot it
"""


def vault(tmp_path, memory=MEMORY, obs=OBS):
    m = tmp_path / "memory"
    m.mkdir(parents=True, exist_ok=True)
    if memory is not None:
        (m / "patterns.md").write_text(memory, encoding="utf-8")
    if obs is not None:
        (m / "observations.md").write_text(obs, encoding="utf-8")
    return tmp_path


def run(v, *args):
    return subprocess.run([sys.executable, "-B", REPEAT, "--vault", str(v), *args], capture_output=True, text=True)


def data(v, *args):
    r = run(v, "--json", *args)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def test_the_selftest_passes():
    r = subprocess.run([sys.executable, "-B", REPEAT, "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "selftest: OK" in r.stdout


def test_a_restated_rule_is_a_repeat_counted_twice(tmp_path):
    d = data(vault(tmp_path))
    (key, rep), = d["repeats"].items()
    assert "shop page" in key and rep["n"] == 2 and rep["dates"] == ["2026-02-10", "2026-02-20"]
    assert len(d["candidates"]) == 1


def test_an_unrelated_correction_matches_nothing(tmp_path):
    d = data(vault(tmp_path, obs="- 2026-02-25: the weather report was in celsius and I wanted fahrenheit\n"))
    assert d["repeats"] == {} and d["candidates"] == []


def test_a_memory_written_after_the_correction_is_not_a_repeat(tmp_path):
    d = data(vault(tmp_path, obs="- 2026-02-01: dishwasher filter check weekly, forgot it\n"))
    assert d["repeats"] == {} and d["near"] == {}


def test_a_correction_within_three_days_of_the_memory_is_near_not_a_repeat(tmp_path):
    d = data(vault(tmp_path, obs="- 2026-01-04: you invented a link to a shop page, open it before you link it\n"))
    assert d["repeats"] == {} and sum(d["near"].values()) == 1 and d["candidates"] == []


def test_one_repeat_plus_a_near_correction_is_a_candidate(tmp_path):
    obs = ("- 2026-01-03: invented a link to a shop page, open it before you link it\n"
           "- 2026-02-10: you invented a link to a shop page again, open it before you link it\n")
    d = data(vault(tmp_path, obs=obs))
    (rep,) = d["repeats"].values()
    assert rep["n"] == 1 and len(d["candidates"]) == 1


def test_fewer_than_three_shared_words_is_not_a_match(tmp_path):
    d = data(vault(tmp_path, obs="- 2026-02-10: shop page broken\n"))
    assert d["repeats"] == {}


def test_accents_and_case_do_not_hide_a_match(tmp_path):
    mem = '- 2026-01-01 | "Nunca inventar link de p\u00e1gina da loja antes de abrir" | chat\n'
    obs = "- 2026-02-10: NUNCA INVENTAR LINK DE PAGINA DA LOJA, abrir antes\n"
    assert len(data(vault(tmp_path, memory=mem, obs=obs))["repeats"]) == 1


def test_the_corrections_file_is_not_read_as_memory(tmp_path):
    d = data(vault(tmp_path))
    assert d["memory"] == 3 and d["corrections"] == 4


def test_a_continuation_line_belongs_to_its_entry(tmp_path):
    mem = '- 2026-01-01 | "never invent"\n  a link to a shop page before you opened it\n'
    obs = "- 2026-02-10: you invented a link to a shop page again, open it before you link it\n"
    assert len(data(vault(tmp_path, memory=mem, obs=obs))["repeats"]) == 1


def test_a_custom_corrections_file_is_read(tmp_path):
    v = vault(tmp_path, obs=None)
    (v / "mine.md").write_text(OBS, encoding="utf-8")
    d = data(v, "--corrections", str(v / "mine.md"))
    assert d["corrections"] == 4 and len(d["repeats"]) == 1


def test_gate_fails_only_with_a_candidate(tmp_path):
    assert run(vault(tmp_path), "--gate").returncode == 1
    clean = vault(tmp_path / "b", obs="- 2026-02-25: the weather report was in celsius\n")
    assert run(clean, "--gate").returncode == 0


def test_the_report_warns_that_the_match_is_lexical(tmp_path):
    r = run(vault(tmp_path))
    assert r.returncode == 0 and "LEXICAL" in r.stdout and "shop page" in r.stdout


def test_the_tool_writes_nothing(tmp_path):
    v = vault(tmp_path)
    before = sorted(p.name for p in v.rglob("*"))
    run(v)
    assert sorted(p.name for p in v.rglob("*")) == before


def test_no_correction_is_not_verified(tmp_path):
    r = run(vault(tmp_path, obs="# nothing dated\n"))
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_no_memory_is_not_verified(tmp_path):
    r = run(vault(tmp_path, memory="# empty\n"))
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_a_missing_corrections_file_is_not_verified(tmp_path):
    assert run(vault(tmp_path, obs=None)).returncode == 3


def test_a_bad_threshold_is_a_usage_error(tmp_path):
    assert run(vault(tmp_path), "--threshold", "0").returncode == 2


def test_only_the_best_older_memory_is_counted(tmp_path):
    mem = ('- 2026-01-01 | "never invent a link to a shop page before you opened it" | chat\n'
           '- 2026-01-02 | "open a link before you send it, check the shop" | chat\n')
    obs = "- 2026-02-10: you invented a link to a shop page again, open it before you link it\n"
    d = data(vault(tmp_path, memory=mem, obs=obs))
    assert sum(r["n"] for r in d["repeats"].values()) == 1


def test_accents_alone_do_not_hide_a_match(tmp_path):
    mem = '- 2026-01-01 | "revisar p\u00e1ginas, \u00f3rg\u00e3o, m\u00e9dico, m\u00fasica, \u00e9pico" | chat\n'
    obs = "- 2026-02-10: revisar paginas, orgao, medico, musica, epico\n"
    assert len(data(vault(tmp_path, memory=mem, obs=obs))["repeats"]) == 1


def test_one_repeat_alone_is_not_a_candidate(tmp_path):
    obs = "- 2026-02-10: you invented a link to a shop page again, open it before you link it\n"
    d = data(vault(tmp_path, obs=obs))
    assert len(d["repeats"]) == 1 and d["candidates"] == []


def test_a_legacy_console_encoding_does_not_crash_the_report(tmp_path):
    # Windows consoles/pipes default to cp1252/cp437: a character outside it ("→") must not raise UnicodeEncodeError.
    mem = MEMORY + '- 2026-04-01 | "never use → in a title" | chat\n'
    obs = OBS + "- 2026-04-02: you used → in a title again, never use → in a title\n"
    v = vault(tmp_path, memory=mem, obs=obs)
    env = {**__import__("os").environ, "PYTHONIOENCODING": "cp1252"}
    r = subprocess.run([sys.executable, "-B", REPEAT, "--vault", str(v), "--json"], capture_output=True, env=env)
    assert r.returncode == 0, r.stderr.decode("cp1252", "replace")
    assert b"UnicodeEncodeError" not in r.stderr


def test_a_legacy_console_encoding_does_not_crash_a_message_on_stderr():
    # stderr under cp1252 with errors=strict: only _safe_stdio keeps "→" from raising
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import repeat as m; m._safe_stdio(); "
            "sys.stderr.write('error → message\\n'); sys.stderr.flush()")
    env = {**__import__("os").environ, "PYTHONIOENCODING": "cp1252:strict"}
    r = subprocess.run([sys.executable, "-B", "-c", code, str(Path(__file__).resolve().parent)],
                       capture_output=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr.decode("cp1252", "replace")
    assert b"UnicodeEncodeError" not in r.stderr
    assert "error ? message".encode("cp1252") in r.stderr
