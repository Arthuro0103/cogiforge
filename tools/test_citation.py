"""Paired tests for citation.py: an invented source is BROKEN, a real one is VERIFIED, and "I could not check" is never OK."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CITATION = str(HERE / "citation.py")
spec = importlib.util.spec_from_file_location("citation", CITATION)
cit = importlib.util.module_from_spec(spec)
sys.modules["citation"] = cit
spec.loader.exec_module(cit)

PAGE = "<html><body><p>In 1986 a total of 860 people; the system wins 77.6% of the time (46.875 Hz floor) with 20 trials.</p><script>999</script></body></html>"
ARXIV_OK = "<feed><opensearch:totalResults>1</opensearch:totalResults><entry><title>Attention Is All You Need</title></entry></feed>"
ARXIV_NONE = "<feed><opensearch:totalResults>0</opensearch:totalResults></feed>"

SCRIPT = {
    "export.arxiv.org/api/query?id_list=1706.03762": (200, ARXIV_OK),
    "export.arxiv.org/api/query?id_list=2401.99999": (200, ARXIV_NONE),
    "export.arxiv.org/api/query?id_list=2401.00001": (503, ""),
    "doi.org/api/handles/10.1000/real": (200, '{"responseCode": 1}'),
    "doi.org/api/handles/10.1000/fake": (404, '{"responseCode":100}'),
    "example.test/page": (200, PAGE),
    "example.test/gone": (404, ""),
    "example.test/post": (405, ""),
    "example.test/down": (0, ""),
    "example.test/error": (500, ""),
}


def fake(url):
    return SCRIPT.get(url.split("://", 1)[1], (0, ""))


def state(kind, target, context="x 5"):
    return cit.check_one({"kind": kind, "target": target, "line": 1, "context": context}, fake)["state"]


def run(*args):
    return subprocess.run([sys.executable, CITATION, *args], capture_output=True, text=True)


def test_an_invented_arxiv_is_broken_and_a_real_one_is_verified():
    assert state("arxiv", "2401.99999", "a paper") == cit.BROKEN
    assert state("arxiv", "1706.03762", "the Attention Is All You Need paper") == cit.VERIFIED


def test_a_real_arxiv_with_the_wrong_subject_is_partial_not_verified():
    assert state("arxiv", "1706.03762", "a study of free range hens") == cit.PARTIAL


def test_an_api_that_did_not_answer_is_not_broken():
    assert state("arxiv", "2401.00001") == cit.NOT_VERIFIED
    assert state("url", "https://example.test/down") == cit.NOT_VERIFIED
    assert state("url", "https://example.test/error") == cit.NOT_VERIFIED


def test_a_doi_that_resolves_is_only_partial_and_one_without_handle_is_broken():
    assert state("doi", "10.1000/real") == cit.PARTIAL
    assert state("doi", "10.1000/fake") == cit.BROKEN


def test_a_dead_page_is_broken_and_a_post_only_endpoint_is_not():
    assert state("url", "https://example.test/gone") == cit.BROKEN
    assert state("url", "https://example.test/post") == cit.PARTIAL


def test_numbers_are_matched_whole_not_as_a_piece_of_another_number():
    page = cit.visible_text(PAGE)
    for n, want in [("86%", False), ("86", False), ("77,6%", True), ("77.6%", True), ("46,875", True), ("20", True), ("2", False), ("77", False)]:
        assert cit.number_on_page(n, page) is want, n


def test_a_percent_needs_the_percent_sign_on_the_page():
    assert not cit.number_on_page("20%", "there were 20 trials")
    assert cit.number_on_page("20%", "there were 20 percent")


def test_one_wrong_number_among_right_ones_is_partial():
    page = cit.visible_text(PAGE)
    assert cit.check_numbers("rate 77,6% with 20 trials", page)[0] == cit.VERIFIED
    assert cit.check_numbers("rate 77,6% with 14 trials", page)[0] == cit.PARTIAL
    assert cit.check_numbers("rate 86%", page)[0] == cit.PARTIAL


def test_a_sentence_with_no_number_cannot_be_verified():
    assert cit.check_numbers("a fine source", "anything")[0] == cit.NOT_VERIFIED


def test_a_number_inside_a_script_does_not_count():
    assert state("url", "https://example.test/page", "it was 999") == cit.PARTIAL


def test_a_year_is_not_a_claim():
    assert cit.claimed_numbers("in 1986 it grew 12%") == ["12%"]


def test_a_short_read_of_the_file_is_not_verified_never_clean(tmp_path, monkeypatch):
    f = tmp_path / "a.md"
    f.write_text("see [s](https://example.test/page) 77.6%\n", encoding="utf-8")
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"see")
    with pytest.raises(OSError):
        cit.read_text(f)
    assert cit.main([str(f), "--no-network"]) == 3


def test_a_date_and_a_url_digit_are_not_claims():
    assert cit.claimed_numbers("on 02/10 and 2026-10-02, 86% see https://x.test/p/123") == ["86%"]


def test_extraction_finds_the_three_kinds_and_nothing_on_a_plain_line():
    items = cit.extract("see [x](https://example.com/a) and arXiv:2401.12345 and 10.1000/xyz123\nplain line\n")
    assert sorted(i["kind"] for i in items) == ["arxiv", "doi", "url"]
    assert all(i["line"] == 1 for i in items)


def test_no_network_never_approves_anything():
    for kind, target in (("url", "https://example.test/page"), ("arxiv", "1706.03762"), ("doi", "10.1000/real")):
        r = cit.check_one({"kind": kind, "target": target, "line": 1, "context": "77.6%"}, None)
        assert r["state"] == cit.NOT_VERIFIED, kind


def test_the_rc_is_typed_and_the_worst_state_wins():
    def r(*s):
        return [{"state": x} for x in s]
    assert cit.exit_code(r(cit.VERIFIED)) == 0
    assert cit.exit_code(r(cit.VERIFIED, cit.PARTIAL, cit.NOT_VERIFIED, cit.BROKEN)) == 1
    assert cit.exit_code(r(cit.PARTIAL, cit.NOT_VERIFIED)) == 3
    assert cit.exit_code(r(cit.VERIFIED, cit.PARTIAL)) == 4


def test_a_file_with_no_citation_is_not_verified_never_clean(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("just text, no sources\n", encoding="utf-8")
    p = run(str(f), "--no-network")
    assert p.returncode == 3 and "NOT_VERIFIED" in p.stdout


def test_the_cli_no_network_is_rc_3_and_json_lists_each_citation(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("it won 77.6% [s](https://example.test/page)\n", encoding="utf-8")
    p = run(str(f), "--no-network", "--json")
    assert p.returncode == 3
    data = json.loads(p.stdout)
    assert [c["state"] for c in data["citations"]] == ["NOT_VERIFIED"]


def test_a_missing_file_is_rc_3_not_a_traceback(tmp_path):
    p = run(str(tmp_path / "missing.md"))
    assert p.returncode == 3 and "NOT_VERIFIED" in p.stdout and "Traceback" not in p.stderr


def test_no_argument_is_a_usage_error():
    assert run().returncode == 2


def test_the_selftest_passes_offline():
    p = run("--selftest")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "selftest OK" in p.stdout


# --- the document is untrusted input: what it can make this tool request, and what it can make it print ---

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/", "http://192.168.1.1/",
    "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://[64:ff9b::7f00:1]/", "http://[::7f00:1]/",
    "http://[2002:7f00:1::]/", "http://0.0.0.0/", "http://100.64.0.1/",
    "file:///etc/passwd", "ftp://example.com/x", "gopher://example.com/",
])
def test_private_literals_and_non_http_schemes_are_not_requested(url):
    assert cit.allowed_url(url) is False
    assert cit.fetch_http(url) == (cit.REFUSED, "")


def test_a_name_that_resolves_to_loopback_is_refused_at_connect():
    assert cit.fetch_http("http://localhost/x") == (cit.REFUSED, "")


def test_a_public_literal_address_is_allowed():
    assert cit.allowed_url("https://8.8.8.8/") is True  # a literal needs no DNS


def test_a_refused_address_is_not_verified_and_says_why():
    item = {"kind": "url", "target": "http://169.254.169.254/", "line": 1, "context": "it has 5 items"}
    out = cit.check_one(item, cit.fetch_http)
    assert out["state"] == cit.NOT_VERIFIED
    assert "not requested" in out["note"]


def test_a_redirect_to_an_internal_address_is_refused():
    import urllib.error
    import urllib.request
    h = cit._GuardedRedirect()
    req = urllib.request.Request("https://example.com/a")
    with pytest.raises(urllib.error.URLError):
        h.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1:8080/admin")


def test_fetches_per_run_are_capped(monkeypatch):
    monkeypatch.setattr(cit, "MAX_FETCHES", 2)
    calls = []

    def counting(url):
        calls.append(url)
        return 200, PAGE

    text = "\n".join(f"it has 77.6% [s](https://example.test/p{i})" for i in range(5))
    res = cit.check_text(text, counting)
    assert len(calls) == 2
    assert [r["state"] for r in res].count(cit.NOT_VERIFIED) == 3
    assert "limit" in res[-1]["note"]


def test_a_huge_file_is_not_read(tmp_path, monkeypatch):
    monkeypatch.setattr(cit, "MAX_FILE_BYTES", 10)
    f = tmp_path / "big.md"
    f.write_text("x" * 100)
    with pytest.raises(OSError):
        cit.read_text(f)


def test_a_dotdot_doi_is_not_requested():
    called = []
    item = {"kind": "doi", "target": "10.1000/../../x", "line": 1, "context": "x"}
    out = cit.check_one(item, lambda u: called.append(u) or (200, ""))
    assert out["state"] == cit.NOT_VERIFIED and not called


def test_control_and_bidi_characters_never_reach_the_output(tmp_path, capsys):
    f = tmp_path / "a.md"
    f.write_text("see https://example.com/\x1b[2J\u202eevil here 5\n", encoding="utf-8")
    for extra in ([], ["--json"]):
        cit.main([str(f), "--no-network", *extra])
        out = capsys.readouterr().out
        assert "\x1b" not in out and "\u202e" not in out


def test_clean_replaces_control_format_and_bidi_characters():
    assert cit.clean("a\x1b[31mb\u202ec\x00d") == "a?[31mb?c?d"


def test_the_address_checked_is_the_address_used(monkeypatch):
    """One lookup, validated, then used: a second resolution is where DNS rebinding lives."""
    import socket
    calls = []

    def rebinding(host, port, *a, **k):
        calls.append(host)
        ip = "93.184.216.34" if len(calls) == 1 else "127.0.0.1"   # public first, loopback after
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    connected = []

    class FakeSock:
        def __init__(self, *a): pass
        def settimeout(self, t): pass
        def connect(self, addr): connected.append(addr); raise OSError("stop here")
        def close(self): pass

    monkeypatch.setattr(socket, "getaddrinfo", rebinding)
    monkeypatch.setattr(socket, "socket", FakeSock)
    cit.fetch_http("http://rebind.example.test/x")
    assert calls == ["rebind.example.test"]                      # resolved exactly once
    assert connected and connected[0][0] == "93.184.216.34"      # and connected to that same address


def test_one_non_public_answer_among_many_refuses_the_name(monkeypatch):
    import socket
    mixed = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
             (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80))]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: mixed)
    with pytest.raises(cit.Refused):
        cit.connect_pinned("mixed.example.test", 80, 1)


@pytest.mark.parametrize("addr,ok", [
    ("8.8.8.8", True), ("2606:4700::1111", True),
    ("127.0.0.1", False), ("100.64.0.1", False), ("::ffff:10.0.0.1", False),
    ("64:ff9b::7f00:1", False), ("::7f00:1", False), ("2002:7f00:1::", False), ("224.0.0.1", False),
    ("::ffff:0:7f00:1", False), ("::ffff:0:0:7f00:1", False), ("fec0::1", False), ("fd00::1", False),
])
def test_public_ip_sees_through_embedded_ipv4(addr, ok):
    import ipaddress
    assert cit.public_ip(ipaddress.ip_address(addr)) is ok


def test_a_slow_fetch_is_cut_by_the_wall_clock(monkeypatch):
    import time
    monkeypatch.setattr(cit, "MAX_SECONDS", 0.2)
    monkeypatch.setattr(cit, "TIMEOUT", 0.1)
    monkeypatch.setattr(cit, "_fetch", lambda url: (time.sleep(3), (200, "late"))[1])
    start = time.monotonic()
    assert cit.fetch_http("https://example.test/slow") == (0, "")
    assert time.monotonic() - start < 1.5


def test_the_run_has_a_wall_clock_budget(monkeypatch):
    monkeypatch.setattr(cit, "MAX_TOTAL_SECONDS", -1)
    res = cit.check_text("it has 77.6% [s](https://example.test/page)", fake)
    assert res[0]["state"] == cit.NOT_VERIFIED and "budget" in res[0]["note"]


def test_hostile_html_is_parsed_in_linear_time():
    import time
    start = time.monotonic()
    for hostile in ("<" * 400_000, "<a " * 130_000, "<script " * 50_000, "<!--" * 100_000, "<script>" * 50_000):
        cit.visible_text(hostile)
    assert time.monotonic() - start < 3


def test_visible_text_keeps_prose_and_drops_markup_script_and_style():
    page = "<p>wins <b>77.6%</b> of 20 trials</p><script>var x = 999;</script><style>.a{}</style><!-- 555 --> a < b"
    got = cit.visible_text(page)
    assert "77.6%" in got and "20" in got and "a < b" in got
    assert "999" not in got and "555" not in got and "<" not in got.replace("a < b", "")


# ---- --quotes: a quote of 5+ words against the vault file linked on the same line ---------------

SOURCE = "I never said I wanted a rest. I said that the work is the only thing that keeps me calm at night.\n"


def quotes_note(tmp_path, line, source=SOURCE):
    (tmp_path / "vault" / "chats").mkdir(parents=True, exist_ok=True)
    (tmp_path / "vault" / "chats" / "c.md").write_text(source, encoding="utf-8")
    note = tmp_path / "vault" / "n.md"
    note.write_text(line + "\n", encoding="utf-8")
    return note


def quote_states(tmp_path, line, source=SOURCE):
    note = quotes_note(tmp_path, line, source)
    return [r["state"] for r in cit.check_quotes(note.read_text(encoding="utf-8"), note, tmp_path / "vault")]


def test_quotes_verified_when_every_stretch_is_in_the_linked_file(tmp_path):
    line = 'He said "the work is the only thing that keeps me calm" in [[chats/c]].'
    assert quote_states(tmp_path, line) == [cit.VERIFIED]


def test_quotes_editorial_brackets_and_ellipsis_are_allowed(tmp_path):
    line = 'He said "the work [of the day] is the only thing ... keeps me calm at night" ([c](chats/c.md)).'
    assert quote_states(tmp_path, line) == [cit.VERIFIED]


def test_quotes_broken_when_a_stretch_is_invented(tmp_path):
    line = 'He said "the work is the only thing that makes me deeply happy" in [[chats/c]].'
    assert quote_states(tmp_path, line) == [cit.BROKEN]


def test_quotes_without_a_link_or_with_a_missing_file_are_not_verified(tmp_path):
    assert quote_states(tmp_path, 'He said "the work is the only thing that keeps me calm" somewhere.') == [cit.NOT_VERIFIED]
    assert quote_states(tmp_path, 'He said "the work is the only thing that keeps me calm" in [[chats/nope]].') == [cit.NOT_VERIFIED]


def test_quotes_short_quotes_and_curly_quotes(tmp_path):
    assert quote_states(tmp_path, 'He said "keeps me calm" in [[chats/c]].') == []
    assert quote_states(tmp_path, 'He said \u201cthe work is the only thing that keeps me calm\u201d in [[chats/c]].') == [cit.VERIFIED]


def test_quotes_cli_uses_the_citation_rc(tmp_path):
    note = quotes_note(tmp_path, 'He said "the work is the only thing that makes me deeply happy" in [[chats/c]].')
    r = subprocess.run([sys.executable, CITATION, "--quotes", str(note), "--vault", str(tmp_path / "vault")], capture_output=True, text=True)
    assert r.returncode == 1 and "BROKEN" in r.stdout
    note.write_text('No quotes here.\n', encoding="utf-8")
    r = subprocess.run([sys.executable, CITATION, "--quotes", str(note), "--vault", str(tmp_path / "vault")], capture_output=True, text=True)
    assert r.returncode == 3 and "NOT_VERIFIED" in r.stdout


def test_quotes_inside_a_fenced_block_are_not_checked(tmp_path):
    line = '```\nHe said "the work is the only thing that makes me deeply happy" in [[chats/c]].\n```'
    assert quote_states(tmp_path, line) == []


def test_quotes_a_link_that_resolves_outside_the_vault_is_not_a_source(tmp_path):
    (tmp_path / "secret.md").write_text(SOURCE, encoding="utf-8")
    note = tmp_path / "vault" / "n.md"
    note.parent.mkdir(parents=True)
    note.write_text('He said "the work is the only thing that keeps me calm" in [[secret]].\n', encoding="utf-8")
    res = cit.check_quotes(note.read_text(encoding="utf-8"), note, tmp_path / "vault")
    assert [r["state"] for r in res] == [cit.NOT_VERIFIED] and "outside the vault" in res[0]["note"]
    (tmp_path / "link.md").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "vault" / "viaLink.md").symlink_to(tmp_path / "link.md")
    note.write_text('He said "the work is the only thing that keeps me calm" in [[viaLink]].\n', encoding="utf-8")
    assert [r["state"] for r in cit.check_quotes(note.read_text(encoding="utf-8"), note, tmp_path / "vault")] == [cit.NOT_VERIFIED]


def test_quotes_every_piece_must_be_there_and_in_the_same_order(tmp_path):
    src = "You should push to main when the tests pass, and never before that, as the team agreed last week.\n"
    assert quote_states(tmp_path, 'He said "never ... push to main" in [[chats/c]].', src) == [cit.BROKEN]  # never comes AFTER
    assert quote_states(tmp_path, 'He said "you should push to main ... as the team agreed last week" in [[chats/c]].', src) == [cit.VERIFIED]
    assert quote_states(tmp_path, 'He said "as the team agreed last week ... you should push to main" in [[chats/c]].', src) == [cit.BROKEN]
    assert quote_states(tmp_path, 'He said "you should push to main ... and never ... agreed last week" in [[chats/c]].', src) == [cit.VERIFIED]
    assert quote_states(tmp_path, 'He said "you should push to main [sic] ... always ... agreed last week" in [[chats/c]].', src) == [cit.BROKEN]


def test_quotes_a_one_word_piece_still_counts():
    import quote as q
    assert q.found_ordered("push ... never", "you should push to main and never before") is True
    assert q.found_ordered("never ... push", "you should push to main and never before") is False
    assert q.found_ordered("[only editorial]", "x") is None
