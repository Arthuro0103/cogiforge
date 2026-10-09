"""Paired tests for ask.py. ASK_PATH points to another copy (used by mutation).

Accented text is written with escapes so the repo's no-Portuguese test has nothing to flag.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ASK = os.environ.get("ASK_PATH") or str(Path(__file__).with_name("ask.py"))
ACAO = "a\u00e7\u00e3o"      # accent-bearing word
CAFE = "caf\u00e9"


def run(*args):
    return subprocess.run([sys.executable, ASK, *args], capture_output=True, text=True)


def write(vault, files):
    for rel, text in files.items():
        p = Path(vault) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Path(vault)


def search(vault, q, *extra):
    r = run("search", q, "--vault", str(vault), "--json", *extra)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def ids(results):
    return [r["id"] for r in results]


def answer(tmp_path, text):
    p = tmp_path / "answer.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


BASE = {
    "notes/focus.md": f"---\narea: life\n---\n# Focus blocks beat long sessions\n\nIntro.\n\n## Morning {ACAO}\n\n"
                      f"Deep work happens before the first {CAFE}.\n\n### Why mornings\n\nLess noise.\n",
    "notes/sleep.md": "# Sleep debt is paid in weeks\n\n## Evidence\n\nSeven hours beat five.\n",
}


def test_accentless_query_finds_accented_text(tmp_path):
    v = write(tmp_path, BASE)
    assert "notes/focus#Morning " + ACAO in ids(search(v, "acao"))
    assert "notes/focus#Morning " + ACAO in ids(search(v, ACAO))
    assert search(v, "zzzunknown") == []  # neighbour passes: a word that is not there finds nothing


def test_queries_in_portuguese_and_english(tmp_path):
    v = write(tmp_path, BASE)
    assert ids(search(v, "work before the " + CAFE))[0] == "notes/focus#Morning " + ACAO
    assert ids(search(v, "o trabalho profundo antes do cafe"))[0] == "notes/focus#Morning " + ACAO
    assert ids(search(v, "how many hours of sleep"))[0] == "notes/sleep#Evidence"


def test_section_path_survives_a_big_section_split(tmp_path):
    paras = "\n\n".join(f"Paragraph {i} " + "word " * 60 for i in range(12))
    v = write(tmp_path, {"notes/big.md": f"# Big note\n\n## Long part\n\n{paras}\n"})
    res = search(v, "paragraph word", "--top", "50")
    assert len(res) > 1
    assert all(r["path"] == "Big note > Long part" and r["id"] == "notes/big#Long part" for r in res)
    assert all(len(r["text"]) <= 1200 for r in res)
    assert all(r["text"].count("Paragraph") >= 1 and r["text"].rstrip().endswith("word") for r in res)


def test_title_weighs_more_than_body(tmp_path):
    # same token counts; the body mention sits in the note that wins a tie by id, so only the 2x path weight reorders them
    v = write(tmp_path, {
        "notes/a.md": "# Other topic\n\n## Soil\n\nplain gardening text about nothing at all here\n",
        "notes/b.md": "# Gardening basics\n\n## Soil\n\nplain filler text about nothing at all here\n",
    })
    assert ids(search(v, "gardening")) == ["notes/b#Soil", "notes/a#Soil"]


def test_order_is_stable_on_ties(tmp_path):
    v = write(tmp_path, {f"notes/{n}.md": "# Same\n\n## Same\n\nidentical words\n" for n in "cab"})
    first = ids(search(v, "identical"))
    assert first == sorted(first) and first == ids(search(v, "identical"))


def test_links_bring_the_neighbour_marked_and_without_them_it_is_absent(tmp_path):
    v = write(tmp_path, {
        "notes/a.md": "# Alpha\n\n## Main\n\nunicorn pointer to [[notes/b#Target]] here\n",
        "notes/b.md": "# Beta\n\n## Target\n\nunrelated words only\n\n## Other\n\nnot pointed\n",
        "notes/c.md": "# Gamma\n\n## Target\n\nsame heading, other note\n",
    })
    assert ids(search(v, "unicorn")) == ["notes/a#Main"]
    res = search(v, "unicorn", "--links")
    assert ids(res) == ["notes/a#Main", "notes/b#Target"]
    assert [r["via"] for r in res] == [None, "link"]


def test_links_accept_md_suffix_and_never_duplicate(tmp_path):
    v = write(tmp_path, {
        "notes/a.md": "# Alpha\n\n## Main\n\nunicorn [[notes/b.md#Target]] [[notes/b#Target]] [[notes/c]]\n",
        "notes/b.md": "# Beta\n\n## Target\n\nunrelated words only\n",
        "notes/c.md": "# Gamma\n\n## Hit\n\nunicorn too\n",
    })
    got = ids(search(v, "unicorn", "--links"))
    assert len(got) == len(set(got))
    assert set(got) == {"notes/a#Main", "notes/b#Target", "notes/c#Hit"}
    assert got.index("notes/c#Hit") < 2  # c#Hit is a direct hit, not repeated as a link
    by = {r["id"]: r["via"] for r in search(v, "unicorn", "--links")}
    assert by["notes/c#Hit"] is None and by["notes/b#Target"] == "link"


def test_links_never_pass_double_top(tmp_path):
    links = " ".join("[[notes/b]]" for _ in range(1))
    body = "\n\n".join(f"## S{i}\n\nitem {i}" for i in range(10))
    v = write(tmp_path, {"notes/a.md": f"# Alpha\n\nunicorn {links}\n", "notes/b.md": f"# Beta\n\n{body}\n"})
    assert len(search(v, "unicorn", "--links", "--top", "2")) <= 4


def test_cite_fails_an_invented_id_and_passes_the_real_one(tmp_path):
    v = write(tmp_path, BASE)
    bad = run("cite", answer(tmp_path, "Claim [[notes/focus#Invented]] and [[notes/ghost]]."), "--vault", str(v))
    assert bad.returncode == 1
    assert "notes/focus#Invented" in bad.stdout and "notes/ghost" in bad.stdout
    good = run("cite", answer(tmp_path, f"Claim [[notes/focus#Morning {ACAO}]] and [[notes/sleep]]."), "--vault", str(v))
    assert good.returncode == 0, good.stdout


def test_one_real_and_one_invented_still_fails(tmp_path):
    v = write(tmp_path, BASE)
    r = run("cite", answer(tmp_path, "A [[notes/sleep#Evidence]] B [[notes/sleep#Nope]]"), "--vault", str(v))
    assert r.returncode == 1 and "Nope" in r.stdout and "Evidence" not in r.stdout.replace("no such heading", "")


def test_answer_without_citation_fails_and_with_one_passes(tmp_path):
    v = write(tmp_path, BASE)
    r = run("cite", answer(tmp_path, "Just prose, no links."), "--vault", str(v))
    assert r.returncode == 1 and "no citations" in r.stdout
    assert run("cite", answer(tmp_path, "Prose [[notes/sleep]]."), "--vault", str(v)).returncode == 0


def test_empty_vault_is_not_verified(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    a = answer(tmp_path, "x [[notes/sleep]]")
    r = run("cite", a, "--vault", str(empty))
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout
    s = run("search", "anything", "--vault", str(empty))
    assert s.returncode == 3 and "NOT_VERIFIED" in s.stdout
    missing = run("cite", a, "--vault", str(tmp_path / "nope"))
    assert missing.returncode == 3
    v = write(tmp_path / "full", BASE)
    assert run("cite", a, "--vault", str(v)).returncode == 0  # neighbour: a real vault is verifiable


def test_heading_missing_in_an_existing_note_fails(tmp_path):
    v = write(tmp_path, BASE)
    assert run("cite", answer(tmp_path, "[[notes/sleep#Missing]]"), "--vault", str(v)).returncode == 1
    assert run("cite", answer(tmp_path, "[[notes/sleep#evidence]]"), "--vault", str(v)).returncode == 0


def test_hidden_folders_and_frontmatter_are_not_indexed(tmp_path):
    v = write(tmp_path, {**BASE, ".trash/old.md": "# Old\n\nzebra\n",
                         "notes/fm.md": "---\nsecretkey: hiddenvalue\n---\n# Visible\n\ntext\n"})
    assert search(v, "zebra") == []
    assert search(v, "hiddenvalue") == []
    assert ids(search(v, "visible")) == ["notes/fm#Visible"]


def test_unreadable_answer_is_not_verified(tmp_path):
    v = write(tmp_path, BASE)
    r = run("cite", str(tmp_path / "missing.md"), "--vault", str(v))
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_ties_break_by_id_not_by_position_in_the_file(tmp_path):
    v = write(tmp_path, {"notes/n.md": "# T\n\n## Zeta\n\nidentical words\n\n## Alpha\n\nidentical words\n"})
    assert ids(search(v, "identical")) == ["notes/n#Alpha", "notes/n#Zeta"]


def test_top_limits_the_results(tmp_path):
    v = write(tmp_path, {f"notes/{n}.md": "# Same\n\n## Same\n\nidentical words\n" for n in "cab"})
    assert len(search(v, "identical")) == 3
    assert ids(search(v, "identical", "--top", "1")) == ["notes/a#Same"]


def test_rare_term_beats_a_repeated_common_one(tmp_path):
    # raw counting would rank the note with three "common" first; BM25 weighs the rare term by idf
    files = {f"notes/f{i}.md": "# F\n\n## S\n\ncommon filler\n" for i in range(10)}
    files["notes/a.md"] = "# A\n\n## S\n\ncommon common common\n"
    files["notes/b.md"] = "# B\n\n## S\n\nrareword filler\n"
    v = write(tmp_path, files)
    assert ids(search(v, "rareword common"))[0] == "notes/b#S"


def test_shorter_chunk_wins_with_the_same_term_frequency(tmp_path):
    v = write(tmp_path, {
        "notes/a.md": "# A\n\n## S\n\nneedle " + "padding " * 40 + "\n",
        "notes/b.md": "# B\n\n## S\n\nneedle\n",
    })
    assert ids(search(v, "needle")) == ["notes/b#S", "notes/a#S"]


def test_stop_words_are_not_searched(tmp_path):
    v = write(tmp_path, BASE)
    assert search(v, "the of and") == []  # "the" is in the text, but it is a stop word


def test_heading_levels_and_section_paths(tmp_path):
    v = write(tmp_path, BASE)
    res = {r["id"]: r for r in search(v, "noise")}
    assert res["notes/focus#Why mornings"]["path"] == f"Focus blocks beat long sessions > Morning {ACAO} > Why mornings"
    v2 = write(tmp_path / "two", {"notes/t.md": "# T\n\n## A\n\nalpha1\n\n## B\n\nbeta1\n\n### C\n\ngamma1\n\n#### Deep\n\ndelta1\n"})
    got = {}
    for q in ("alpha1", "beta1", "gamma1", "delta1"):
        got.update({r["id"]: r["path"] for r in search(v2, q)})
    assert got == {"notes/t#A": "T > A", "notes/t#B": "T > B", "notes/t#C": "T > B > C"}  # H4 stays inside C


def test_the_first_h1_is_the_title_not_a_section(tmp_path):
    v = write(tmp_path, {"notes/t.md": "# First\n\nintro1\n\n# Second\n\nbody1\n"})
    assert [(r["id"], r["path"]) for r in search(v, "intro1")] == [("notes/t#First", "First")]
    assert [(r["id"], r["path"]) for r in search(v, "body1")] == [("notes/t#Second", "First > Second")]


def test_headings_inside_code_fences_are_not_headings(tmp_path):
    v = write(tmp_path, {"notes/f.md": "# Real\n\n## S\n\ntext\n\n```\n# fake heading\ncode line\n```\n\nmore\n"})
    res = search(v, "code line")
    assert ids(res) == ["notes/f#S"] and "# fake heading" in res[0]["text"]
    assert run("cite", answer(tmp_path, "[[notes/f#fake heading]]"), "--vault", str(v)).returncode == 1
    assert run("cite", answer(tmp_path, "[[notes/f#S]]"), "--vault", str(v)).returncode == 0


def test_cite_accepts_file_name_heading_block_refs_and_md_suffix(tmp_path):
    v = write(tmp_path, {**BASE, "notes/plain.md": "no heading here\n"})
    assert ids(search(v, "heading here")) == ["notes/plain#plain"]
    for cite in ("[[notes/plain#plain]]", "[[notes/sleep#^abc123]]", "[[notes/sleep.md]]", "[[notes/sleep.md#Evidence|alias]]"):
        r = run("cite", answer(tmp_path, cite), "--vault", str(v))
        assert r.returncode == 0, (cite, r.stdout)


def test_cite_rejects_hidden_folders_and_reports_each_failure_once(tmp_path):
    v = write(tmp_path, {**BASE, ".trash/old.md": "# Old\n\nzebra\n"})
    r = run("cite", answer(tmp_path, "[[.trash/old]]"), "--vault", str(v))
    assert r.returncode == 1 and "does not exist" in r.stdout
    r = run("cite", answer(tmp_path, "[[notes/sleep#Nope]] again [[notes/sleep#Nope]]"), "--vault", str(v))
    assert r.returncode == 1 and r.stdout.count("FAIL") == 1
    ok = run("cite", answer(tmp_path, "[[notes/sleep]] [[notes/sleep]] [[notes/focus]]"), "--vault", str(v))
    assert ok.returncode == 0 and "2 distinct" in ok.stdout


def test_unreadable_files_are_skipped_loudly_not_fatal(tmp_path):
    v = write(tmp_path, BASE)
    (v / "notes" / "bad.md").write_bytes(b"\xff\xfe\x00 not utf-8 \xc3\x28")
    r = run("search", "sleep", "--vault", str(v), "--json")
    assert r.returncode == 0 and "notes/sleep#Evidence" in r.stdout
    assert "skipped notes/bad.md" in r.stderr


def test_a_link_written_with_the_md_suffix_still_resolves(tmp_path):
    v = write(tmp_path, {
        "notes/a.md": "# Alpha\n\n## Main\n\nunicorn [[notes/b.md#Target]]\n",
        "notes/b.md": "# Beta\n\n## Target\n\nunrelated words only\n",
    })
    assert ids(search(v, "unicorn", "--links")) == ["notes/a#Main", "notes/b#Target"]


# ---- cite --log: the use of a note is recorded only when the answer was real -----------------

LOGGED = {"notes/a.md": "# Alpha\n\n## Part one\n\ntext about alpha\n", "notes/b.md": "# Beta\n\nbeta text\n"}


def cite_log(tmp_path, answer, *extra):
    v = write(tmp_path / "v", LOGGED)
    f = tmp_path / "answer.md"
    f.write_text(answer, encoding="utf-8")
    return v, run("cite", str(f), "--vault", str(v), *extra)


def log_rows(vault):
    f = Path(vault) / "memory" / "ask-log.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def test_cite_log_records_one_line_with_the_cited_notes(tmp_path):
    v, r = cite_log(tmp_path, "x [[notes/a#Part one]] and [[notes/b]] and [[notes/a]]\n", "--log", "--today", "2026-10-08")
    assert r.returncode == 0 and "logged in memory/ask-log.jsonl" in r.stdout
    assert log_rows(v) == [{"date": "2026-10-08", "cited": ["notes/a", "notes/b"]}]


def test_cite_log_appends_a_line_per_consultation(tmp_path):
    v, _ = cite_log(tmp_path, "x [[notes/a]]\n", "--log", "--today", "2026-10-01")
    f = tmp_path / "answer.md"
    run("cite", str(f), "--vault", str(v), "--log", "--today", "2026-10-02")
    assert [r["date"] for r in log_rows(v)] == ["2026-10-01", "2026-10-02"]


def test_a_failed_citation_logs_nothing(tmp_path):
    v, r = cite_log(tmp_path, "x [[notes/a]] and [[notes/missing]]\n", "--log")
    assert r.returncode == 1 and log_rows(v) == []


def test_an_answer_with_no_citation_logs_nothing(tmp_path):
    v, r = cite_log(tmp_path, "an answer with no citation\n", "--log")
    assert r.returncode == 1 and log_rows(v) == []


def test_without_log_nothing_is_written(tmp_path):
    v, r = cite_log(tmp_path, "x [[notes/a]]\n")
    assert r.returncode == 0 and log_rows(v) == [] and not (v / "memory").exists()


def test_search_never_writes_a_log(tmp_path):
    v = write(tmp_path / "v", LOGGED)
    assert run("search", "alpha", "--vault", str(v)).returncode == 0
    assert not (v / "memory").exists()


def test_the_log_row_has_only_the_date_and_the_cited_notes(tmp_path):
    # privacy: the question text can hold something private, so it is never persisted
    v, _ = cite_log(tmp_path, "x [[notes/a]]\n", "--log")
    assert set(log_rows(v)[0]) == {"date", "cited"}


def test_log_does_not_take_the_question_text_anymore(tmp_path):
    v, r = cite_log(tmp_path, "x [[notes/a]]\n", "--log", "my private question")
    assert r.returncode == 2 and log_rows(v) == []


def test_the_date_defaults_to_today(tmp_path):
    import datetime
    v, _ = cite_log(tmp_path, "x [[notes/a]]\n", "--log")
    assert log_rows(v)[0]["date"] == datetime.date.today().isoformat()


def test_an_unreadable_vault_logs_nothing_and_is_not_verified(tmp_path):
    f = tmp_path / "answer.md"
    f.write_text("x [[notes/a]]\n", encoding="utf-8")
    r = run("cite", str(f), "--vault", str(tmp_path / "empty"), "--log")
    assert r.returncode == 3 and not (tmp_path / "empty").exists()
