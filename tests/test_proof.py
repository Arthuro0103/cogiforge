"""Paired tests for core/proof.py: a check that touched nothing cannot say OK, and a null always has a reason."""
import subprocess
import sys
from pathlib import Path

import pytest

import proof
from proof import (ERROR, FAILED, NOT_VERIFIED, VERIFIED, Measure, Reason, ReasonMissing, Record, Verdict,
                   scoreboard, verify)

PROOF = str(Path(__file__).resolve().parent.parent / "core" / "proof.py")


def folder(tmp_path, name, files):
    d = tmp_path / name
    d.mkdir()
    for fn, text in files.items():
        (d / fn).write_text(text, encoding="utf-8")
    return d


def test_a_check_that_touched_nothing_is_not_verified_whatever_it_returns():
    for returned in (True, False, None):
        v = verify("lies", lambda rec, r=returned: r)
        assert v.status == NOT_VERIFIED and not v.touches and v.reason is Reason.FAILED
        assert not v.counts_as_ok


def test_a_check_that_read_a_file_can_pass_and_can_fail(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    assert verify("pass", lambda r: "hello" in r.read_file(f)).status == VERIFIED
    bad = verify("fail", lambda r: "absent" in r.read_file(f))
    assert bad.status == FAILED and bad.reason is Reason.SINGLE and not bad.counts_as_ok


def test_a_check_that_returns_none_did_not_conclude(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    v = verify("undecided", lambda r: (r.read_file(f), None)[1])
    assert v.status == NOT_VERIFIED and v.reason is Reason.FAILED and v.touches


def test_the_five_reasons_of_a_single_file_measure(tmp_path):
    rec = Record()
    one = rec.single_file(folder(tmp_path, "one", {"a.md": "x" * 50}))
    assert one.reason is Reason.SINGLE and one.value == "x" * 50
    assert rec.single_file(folder(tmp_path, "empty", {})).reason is Reason.NOTHING_TO_MEASURE
    assert rec.single_file(folder(tmp_path, "two", {"a.md": "a", "b.md": "b"})).reason is Reason.MULTIPLE
    assert rec.single_file(tmp_path / "missing").reason is Reason.FAILED


def test_ran_and_found_nothing_is_not_the_same_reason_as_did_not_run(tmp_path):
    ran = verify("empty", lambda r: r.single_file(folder(tmp_path, "empty", {})))
    never = verify("missing", lambda r: r.single_file(tmp_path / "missing"))
    assert ran.status == never.status == NOT_VERIFIED
    assert ran.reason is Reason.NOTHING_TO_MEASURE and never.reason is Reason.FAILED


def test_a_placeholder_with_a_size_and_no_content_is_the_wrong_type(tmp_path, monkeypatch):
    d = folder(tmp_path, "one", {"a.md": "x" * 100})
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"")
    m = Record().single_file(d)
    assert m.reason is Reason.WRONG_TYPE and not m.has_value
    v = verify("direct read", lambda r: r.read_file(d / "a.md"))
    assert v.status == NOT_VERIFIED and v.reason is Reason.WRONG_TYPE


def test_a_short_read_is_an_error_not_a_pass(tmp_path, monkeypatch):
    f = tmp_path / "a.txt"
    f.write_text("0123456789", encoding="utf-8")
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"0123")
    v = verify("short", lambda r: True if r.read_file(f) else False)
    assert v.status == ERROR and v.reason is Reason.FAILED


def test_a_measured_value_is_verified_even_when_the_value_is_falsy(tmp_path):
    d = folder(tmp_path, "one", {"a.md": ""})
    v = verify("empty file", lambda r: r.single_file(d))
    assert v.status == VERIFIED and v.reason is Reason.SINGLE


def test_a_check_that_raises_is_an_error_with_a_reason():
    v = verify("boom", lambda r: 1 / 0)
    assert v.status == ERROR and v.reason is Reason.FAILED and "ZeroDivisionError" in v.note


def test_a_null_verdict_without_a_reason_raises():
    for status in (NOT_VERIFIED, ERROR):
        with pytest.raises(ReasonMissing):
            Verdict("x", status)


def test_a_null_verdict_cannot_claim_the_reason_single():
    with pytest.raises(ReasonMissing):
        Verdict("x", NOT_VERIFIED, reason=Reason.SINGLE)


def test_a_concluded_verdict_cannot_carry_a_null_reason():
    with pytest.raises(ReasonMissing):
        Verdict("x", VERIFIED, reason=Reason.MULTIPLE)
    assert Verdict("x", VERIFIED).reason is Reason.SINGLE


def test_a_measure_refuses_to_contradict_itself():
    with pytest.raises(ReasonMissing):
        Measure(None, "single")  # a string is not a typed reason
    with pytest.raises(ReasonMissing):
        Measure(None, Reason.SINGLE)
    with pytest.raises(ReasonMissing):
        Measure("value", Reason.MULTIPLE)
    assert Measure("v", Reason.SINGLE).has_value


def test_the_reason_names_are_the_five_and_only_the_five():
    assert [r.value for r in Reason] == ["single", "multiple", "nothing_to_measure", "wrong_type", "failed"]


def test_the_scoreboard_has_four_columns_and_does_not_forgive_a_null(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    ok = verify("ok", lambda r: "hello" in r.read_file(f))
    text, rc = scoreboard([ok])
    assert rc == 0 and "1 verified, 0 failed, 0 NOT_VERIFIED, 0 error" in text
    text, rc = scoreboard([ok, verify("lies", lambda r: True)])
    assert rc == 1 and "1 NOT_VERIFIED" in text and "touched: NOTHING" in text and "reasons: 1 failed" in text
    text, rc = scoreboard([verify("boom", lambda r: 1 / 0)])
    assert rc == 1 and "1 error" in text


def test_the_scoreboard_prints_the_reason_of_a_null(tmp_path):
    text, _ = scoreboard([verify("empty", lambda r: r.single_file(folder(tmp_path, "e", {})))])
    assert "[nothing_to_measure]" in text


def test_the_scoreboard_detail_lists_what_was_touched(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    text, _ = scoreboard([verify("ok", lambda r: "hello" in r.read_file(f))], detail=True)
    assert "touched: file:" in text and "5 bytes read" in text


def test_a_command_is_recorded_with_its_rc_and_output_size():
    rec = Record()
    r = rec.run([sys.executable, "-c", "print('hi')"])
    assert r.returncode == 0 and len(rec) == 1
    assert "rc=0" in str(rec.touches[0]) and "3B stdout" in str(rec.touches[0])


def test_the_selftest_passes():
    p = subprocess.run([sys.executable, PROOF, "--selftest"], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "selftest: OK" in p.stdout


def test_no_argument_is_a_usage_error():
    assert subprocess.run([sys.executable, PROOF], capture_output=True, text=True).returncode == 2
