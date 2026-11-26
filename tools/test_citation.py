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


# ---- a quote on a line with a web link: it has to be literally on THAT page ----------------------

WEB = ("<html><body><h1>Harbour log</h1><p>The lighthouse keeper counted 412 gulls over the long winter and "
       "wrote that the north wall leaks whenever the tide runs high.</p></body></html>")
LINK = "[log](https://pages.test/log)"
REAL = "the north wall leaks whenever the tide runs high"
INVENTED = "the south wall holds even when the tide runs high"


def judge(line, page=WEB, status=200, which=0):
    return cit.check_one(cit.extract(line)[which], lambda url: (status, page))


def verdict(line, page=WEB, status=200):
    return judge(line, page, status)["state"]


def said(quote, page=WEB):
    return verdict(f'It says "{quote}" {LINK}', page)


def test_a_literal_quote_is_verified_without_any_number():
    r = judge(f'It says "{REAL}" {LINK}')
    assert (r["state"], r["note"]) == (cit.VERIFIED, "every quote (1) is literally on the page")


def test_an_invented_quote_is_partial_and_the_note_shows_it():
    r = judge(f'It says "{INVENTED}" {LINK}')
    assert r["state"] == cit.PARTIAL
    assert "NOT found literally" in r["note"] and "the south wall holds" in r["note"]


def test_only_the_page_linked_on_that_line_counts():
    pages = {"https://pages.test/log": "<p>A page about bread ovens and nothing else at all.</p>",
             "https://pages.test/other": WEB}
    text = f'It says "{REAL}" {LINK}\nSee also [other](https://pages.test/other)\n'
    res = cit.check_text(text, lambda url: (200, pages[url]))
    assert res[0]["state"] == cit.PARTIAL and res[1]["state"] == cit.NOT_VERIFIED


def test_each_page_of_a_line_is_searched_alone_and_the_note_says_so():
    pages = {"https://pages.test/log": WEB, "https://pages.test/other": "<p>bread ovens</p>"}
    res = cit.check_text(f'It says "{REAL}" {LINK} [other](https://pages.test/other)', lambda url: (200, pages[url]))
    assert [r["state"] for r in res] == [cit.VERIFIED, cit.PARTIAL]
    assert all("the line links 2 pages" in r["note"] for r in res)
    assert "pages and each" not in judge(f'It says "{REAL}" {LINK}')["note"]
    assert "pages and each" not in judge(f'It says "{REAL}" {LINK} and again {LINK}')["note"]


def test_a_quote_on_a_line_with_no_web_link_is_left_alone():
    text = f'It says "{INVENTED}" arXiv:1706.03762, Attention Is All You Need\n'
    res = cit.check_text(text, fake)
    assert [(r["state"], "quote" in r["note"]) for r in res] == [(cit.VERIFIED, False)]
    res = cit.check_text(f'It says "{INVENTED}" doi 10.1000/real', fake)
    assert res[0]["note"] == "the DOI resolves; what the sentence claims was not checked"
    assert cit.check_text(f'"{INVENTED}"\n[log](https://example.test/page) 77.6%', fake)[0]["state"] == cit.VERIFIED


@pytest.mark.parametrize("opening,closing", [('"', '"'), ("\u201c", "\u201d"), ("\u00ab", "\u00bb"), ("\u2018", "\u2019")])
def test_every_kind_of_quotation_mark_is_read(opening, closing):
    assert verdict(f"It says {opening}{REAL}{closing} {LINK}") == cit.VERIFIED
    assert verdict(f"It says {opening}{INVENTED}{closing} {LINK}") == cit.PARTIAL


@pytest.mark.parametrize("line", [
    f'\u201cThe keeper wrote that \u201c{INVENTED}\u201d in the log\u201d',
    f'"The keeper wrote that "{INVENTED}" in the log"',
    f'\u00abThe keeper wrote \u2018{INVENTED}\u2019 there\u00bb',
    f'\u201c"{INVENTED}" is what the keeper wrote\u201d',
])
def test_nested_quotes_are_checked_at_every_depth(line):
    quotes, unmatched = cit.line_quotes(line)
    assert INVENTED in quotes and len(quotes) == 2 and not unmatched


def test_a_nested_quote_matches_a_page_that_marks_it_differently():
    page = "<p>The keeper called it \u201cthe leaking north wall\u201d in every report.</p>"
    for line in ('\u201cThe keeper called it \u2018the leaking north wall\u2019 in every report\u201d',
                 '"The keeper called it "the leaking north wall" in every report"',
                 "\u00abThe keeper called it 'the leaking north wall' in every report\u00bb"):
        assert verdict(f"{line} {LINK}", page) == cit.VERIFIED, line


def test_an_apostrophe_inside_a_word_is_not_a_quotation_mark():
    inside = "I don\u2019t know why the keeper\u2019s lamp went dark"
    assert cit.line_quotes(f"\u2018{inside}\u2019") == ([inside], False)
    page = "<p>I don't know why the keeper's lamp went dark that night.</p>"
    assert verdict(f"\u2018{inside}\u2019 {LINK}", page) == cit.VERIFIED
    assert cit.line_quotes("rock \u2019n\u2019 roll, Hawai\u2018i and the keeper\u2019s old brass lamp are here") == ([], False)


def test_an_apostrophe_that_differs_is_a_different_word():
    assert said("the gulls know its nest very well", "<p>the gulls know it's nest very well</p>") == cit.PARTIAL


def test_a_plural_apostrophe_that_closes_early_never_verifies():
    page = "<p>we read all of the keepers notes</p>"
    r = judge(f"\u2018we read all of the keepers\u2019 notes and then invented this\u2019 {LINK}", page)
    assert r["state"] == cit.PARTIAL and "no pair" in r["note"]
    assert cit.line_quotes("\u2018one two three four five\u2019 and the keepers\u2019 lamp")[1] is False


@pytest.mark.parametrize("mark", ["...", "\u2026", "[...]", "[\u2026]", "(...)", "(\u2026)", "[ ... ]", "...."])
def test_an_elision_may_cut_words(mark):
    r = judge(f'"The lighthouse keeper counted {mark} the north wall leaks" {LINK}')
    assert r["state"] == cit.VERIFIED and "elision" in r["note"]
    assert said(f"The lighthouse keeper counted {mark} the south wall holds") == cit.PARTIAL


def test_an_elision_glued_to_a_word_does_not_eat_the_word():
    assert said("The lighthouse keeper counted[...] the north wall leaks") == cit.VERIFIED
    assert said("The lighthouse keeper invented[...] the north wall leaks") == cit.PARTIAL


def test_stretches_must_come_in_the_order_of_the_page_and_not_overlap():
    assert said("the north wall leaks ... The lighthouse keeper counted") == cit.PARTIAL
    assert said("the north wall leaks ... wall leaks whenever the tide") == cit.PARTIAL
    assert said("the north wall leaks ... whenever the tide runs") == cit.VERIFIED


def test_without_an_elision_the_note_does_not_mention_one():
    assert "elision" not in judge(f'"{REAL}" {LINK}')["note"]


@pytest.mark.parametrize("quote", [
    "the north wall [of the tower] leaks whenever the tide runs high",
    "[The old keeper] wrote that the north wall leaks",
    "[T]he lighthouse keeper counted 412 gulls",
    "the north wall leaks whenever the tide run[ning] high [sic]",
])
def test_an_editorial_insertion_caps_the_result_at_partial(quote):
    r = judge(f'"{quote}" {LINK}')
    assert r["state"] == cit.PARTIAL and "editorial insertion" in r["note"] and "NOT found" not in r["note"]


def test_an_editorial_insertion_does_not_hide_an_invented_stretch():
    r = judge(f'"the south wall [sic] holds even when the tide" {LINK}')
    assert r["state"] == cit.PARTIAL and "NOT found" in r["note"]


@pytest.mark.parametrize("quote", [
    "possible to count every gull on the roof",   # the page says `impossible`
    "impossible to count every gull on the roo",  # cut in the middle of the last word
])
def test_a_stretch_is_matched_as_whole_words(quote):
    assert said(quote, "<p>It is impossible to count every gull on the roof.</p>") == cit.PARTIAL


@pytest.mark.parametrize("page,quote,found", [
    ("the keeper is a well-known figure", "known figure the keeper", False),
    ("the keeper is a well-known figure", "the keeper is a well", False),
    ("the keeper is a well- known figure", "the keeper is a well", True),
    ("the keeper lit John's old lamp", "the keeper lit John", False),
    ("the keeper lit John' old lamp", "the keeper lit John", True),
    ("it rose by 3.5 metres in a day", "metres in a day", True),
    ("the tide rose by 3.5 metres", "the tide rose by 3", False),
    ("the tide rose by 3, then fell", "the tide rose by 3", True),
    ("level 2.5 of the tide gauge broke", "5 of the tide gauge", False),
    ("level two,5 of the tide gauge broke", "5 of the tide gauge", True),
    ("-5 degrees at the tower", "5 degrees at the tower", False),
    ("it was -5 degrees at the tower", "5 degrees at the tower", False),
    ("it was (\u22125 degrees at the tower)", "5 degrees at the tower", False),
    ("it was -5 degrees at the tower", "-5 degrees at the tower", True),
    ("pages 4-5 degrees at the tower", "5 degrees at the tower", False),
    ("it was -five degrees at the tower", "five degrees at the tower", True),
    ("snake_case names are used here", "case names are used", False),
    ("unlit lamps stay on the shelf. lit lamps stay on the desk", "lit lamps stay on the desk", True),
])
def test_word_and_number_boundaries(page, quote, found):
    assert cit.in_order([cit.literal(quote)], cit.literal(page)) is found


def test_a_combining_mark_belongs_to_its_word():
    assert cit.in_order(["say k"], "say k\u093f now") is False


@pytest.mark.parametrize("page", [
    "<p>THE NORTH WALL LEAKS WHENEVER THE TIDE RUNS HIGH</p>",
    "<p>the north&nbsp;wall\n   leaks whenever the <em>tide</em> runs high</p>",
    "<p>the north wall leaks whenever the ti<b>de</b> r<wbr>uns h<span class='x'>igh</span></p>",
    "<p>the north wall leaks when\u00adever the ti&#8203;de runs hi\ufeffgh</p>",
    '<p>the north wall <a href="/x">leaks</a>, whenever the tide runs high</p>',
    "<p>the &quot;north&quot; wall leaks whenever the tide runs high</p>",
])
def test_markup_entities_case_and_invisible_characters_do_not_matter(page):
    assert said(REAL if "</a>," not in page else "wall leaks, whenever the tide", page) == cit.VERIFIED


@pytest.mark.parametrize("page", [
    "<p>the north wall leaks when</p><p>ever the tide runs high</p>",
    "<p>the north wall leaks when<br>ever the tide runs high</p>",
    "<p>the north wall leaks when<a-card></a-card>ever the tide runs high</p>",
    "<p>the north wall leaks whenever the tide runs low</p><script>var s = 'the north wall leaks whenever the tide runs high'</script>",
    "<!-- the north wall leaks whenever the tide runs high --><p>nothing</p>",
    '<p title="the north wall leaks whenever the tide runs high">nothing</p>',
])
def test_what_is_not_on_the_page_as_text_is_not_found(page):
    assert said(REAL, page) == cit.PARTIAL


def test_a_tag_inside_the_page_text_with_a_slash_or_a_space_is_still_inline():
    assert cit.visible_text("a<b/>c<i\n x>d</i>e<a-b>f", cit.INLINE_TAGS) == "acde f"
    assert cit.visible_text("a<b>c</b>d") == "a c d"  # the number check keeps its spacing


@pytest.mark.parametrize("page,quote", [
    ("calm\u2014and that matters\u2014at night", "calm \u2014 and that matters - at night"),
    ("calm \u2013 and that matters a lot -- at night", "calm\u2014and that matters a lot\u2014at night"),
    ("the years 1910\u20131920 were wet", "the years 1910-1920 were wet"),
    ("a well\u2011kept lamp on the stairs", "a well-kept lamp on the stairs"),
    ("a well\u2010kept lamp on the stairs", "a well-kept lamp on the stairs"),
    ("Caf\u00e9 owners fed the gulls daily", "Cafe\u0301 owners fed the gulls daily"),
])
def test_dash_style_and_unicode_form_do_not_matter(page, quote):
    assert said(quote, f"<p>{page}</p>") == cit.VERIFIED


def test_an_apostrophe_after_a_decomposed_letter_is_still_inside_the_word():
    page = "<p>Jose\u0301\u2019s lamp burned all night</p>"
    assert said("Jos\u00e9's lamp burned all night", page) == cit.VERIFIED


def test_accents_and_inner_punctuation_do_matter():
    assert said("Cafe owners fed the gulls daily", "<p>Caf\u00e9 owners fed the gulls daily</p>") == cit.PARTIAL
    assert said("no, the keeper stayed at home", "<p>no the keeper stayed at home</p>") == cit.PARTIAL


@pytest.mark.parametrize("quote", [
    f"{REAL}.", f"{REAL}!?", f"\u2014 {REAL};", "the north wall leaks *whenever* the tide runs high",
    "the north wall **_leaks_** whenever the tide runs high", "the north wall `leaks` whenever the tide runs high",
    "the north wall [leaks](https://pages.test/log) whenever the tide runs high",
    "the north wall <em>leaks</em> whenever the tide runs high",
    "the north wall leaks whenever the ti<b>de</b> runs high",
    "the north wall leaks<br>whenever the tide runs high",
])
def test_punctuation_at_the_edges_and_markdown_in_the_note_do_not_matter(quote):
    assert said(quote) == cit.VERIFIED


def test_literal_asterisks_and_snake_case_are_not_emphasis():
    assert said("set max_wall_height to 3 * 4 metres", "<p>set max_wall_height to 3 * 4 metres</p>") == cit.VERIFIED


@pytest.mark.parametrize("line", [
    f'<span title="{INVENTED}">log</span> {LINK}',
    f'[log](https://pages.test/log "{INVENTED}")',
    f"[log](https://pages.test/log '{INVENTED}') and \u2018",
    f'`"{INVENTED}"` {LINK}',
    f"https://pages.test/log?q=%22 {LINK}",
    f"The keeper owns a 13\" screen and a 15\" screen for the gulls {LINK}",
    f"Home \u00bb Logs \u00bb the keeper and the gulls of winter {LINK}",
    f"If a <- b and b <= c then the keeper \u201cwins\u201d {LINK}",
])
def test_things_that_are_not_quotes(line):
    assert cit.line_quotes(line) == ([], False)


def test_marks_around_comparisons_are_not_swallowed_as_tags():
    assert cit.line_quotes(f'if a <b and "{INVENTED}" > c') == ([INVENTED], False)
    assert cit.line_quotes(f'width <= 4 "{INVENTED}" x >= 3') == ([INVENTED], False)
    tag = f'<img src="a.png" alt="{INVENTED}" hidden data-x=1 /><br/><p class=\'y\' >'
    assert cit.line_quotes(tag) == ([], False)


def test_a_link_label_and_a_url_glued_to_the_closing_mark():
    assert cit.line_quotes(f'["{REAL}" in the log](https://pages.test/a_(b))') == ([REAL], False)
    assert cit.line_quotes(f"\u2018{REAL} https://pages.test/log\u2019") == ([REAL], False)
    assert cit.line_quotes(f'"{REAL} https://pages.test/log" ok') == ([REAL], False)


def test_inches_inside_or_outside_a_quote():
    q = "the keeper bought a 13\" screen"
    assert cit.line_quotes(f"\u00ab{q} for the tower\u00bb") == ([f"{q} for the tower"], False)
    assert cit.line_quotes(f'"it was built to last until 2030" {LINK}') == (["it was built to last until 2030"], False)
    assert cit.line_quotes(f'Screen 13" says "{REAL}"') == ([REAL], False)


@pytest.mark.parametrize("line", [
    f'Says:"{REAL}"', f'("{REAL}")', f'[ "{REAL}" ]', f'word\u2014"{REAL}"', f'\u201c{REAL}" mixed', f'"{REAL}\u201d mixed',
])
def test_how_a_straight_quote_opens_and_closes(line):
    assert cit.line_quotes(line) == ([REAL], False)


@pytest.mark.parametrize("line", [
    f'"{INVENTED}', f"\u201c{INVENTED}", f"\u00ab{INVENTED}", f"\u2018{INVENTED}", f"{INVENTED}\u201d",
    f'{INVENTED} "', f'"{INVENTED} \u201cand a closed one inside here\u201d', f'"one \u2018{INVENTED}"',
])
def test_a_mark_without_a_pair_around_five_words_never_verifies(line):
    assert cit.line_quotes(line)[1] is True
    full = judge(f"{LINK} 412 gulls. {line}")
    assert full["state"] != cit.VERIFIED and "no pair" in full["note"]


def test_an_unmatched_mark_downgrades_a_verified_number_to_partial():
    r = judge(f'412 gulls {LINK} "{INVENTED}')
    assert r["state"] == cit.PARTIAL and "no pair" in r["note"]


def test_an_unmatched_mark_around_few_words_changes_nothing():
    line = f'412 gulls {LINK} and then "one two'
    assert cit.line_quotes(line) == ([], False)
    assert judge(line)["state"] == cit.VERIFIED


def test_too_deep_nesting_is_unmatched_not_slow():
    import time
    start = time.monotonic()
    line = "\u2018" * 20_000 + " one two three four five " + "\u201d " * 20_000
    assert cit.line_quotes(line)[1] is True
    assert time.monotonic() - start < 2
    deep = "\u201c" * (cit.MAX_NESTING + 1) + REAL + "\u201d" * (cit.MAX_NESTING + 1)
    assert cit.line_quotes(deep)[1] is True


@pytest.mark.parametrize("hostile", [
    "[](" + " " * 60_000, "[a](u \"" * 8_000, "a" * 100_000 + " [", "*a " * 30_000, "<a " * 30_000, "`" * 60_000,
    '"' + "a" * 60_000 + '"', "[" * 60_000,
])
def test_a_hostile_line_is_read_in_linear_time(hostile):
    import time
    start = time.monotonic()
    quotes, _ = cit.line_quotes(hostile)
    for q in quotes:
        cit.split_quote(q)
    cit.split_quote(hostile)
    assert time.monotonic() - start < 15  # quadratic would take minutes


def test_five_words_make_a_quote_and_four_do_not():
    assert cit.line_quotes('"one two three four"') == ([], False)
    assert cit.line_quotes('"one two three four five"') == (["one two three four five"], False)
    assert cit.line_quotes('"one \u2014 two ... three four"') == ([], False)  # punctuation is not a word


def test_a_quote_with_only_tiny_stretches_is_not_verified():
    r = judge(f'"the ... wall ... the ... tide ... high" {LINK}')
    assert r["state"] == cit.NOT_VERIFIED and "3+ words" in r["note"]
    assert said("the ... wall ... the tide runs high") == cit.VERIFIED


def test_only_so_many_quotes_per_line_are_judged(monkeypatch):
    monkeypatch.setattr(cit, "MAX_LINE_QUOTES", 1)
    r = judge(f'"{REAL}" and "The lighthouse keeper counted 412 gulls" {LINK}')
    assert r["state"] == cit.NOT_VERIFIED and "first 1 quotes" in r["note"]
    assert judge(f'"{REAL}" {LINK}')["state"] == cit.VERIFIED


def test_the_same_quote_twice_counts_once():
    assert "(1)" in judge(f'"{REAL}" and \u201c{REAL}\u201d {LINK}')["note"]


def test_one_bad_quote_among_good_ones_is_partial_and_the_worst_note_comes_first():
    r = judge(f'"{REAL}" and "{INVENTED}" {LINK}')
    assert r["state"] == cit.PARTIAL and r["note"].startswith("quote NOT found")
    r = judge(f'"{INVENTED}" and "a ... b ... c ... d ... e" {LINK}')
    assert r["state"] == cit.NOT_VERIFIED and r["note"].startswith("quote NOT checked") and "NOT found" in r["note"]


def test_with_numbers_and_a_quote_the_worst_result_wins():
    ok = judge(f'412 gulls: "{REAL}" {LINK}')
    assert ok["state"] == cit.VERIFIED and "literally" in ok["note"] and "every number" in ok["note"]
    wrong_number = judge(f'987 gulls: "{REAL}" {LINK}')
    assert wrong_number["state"] == cit.PARTIAL and "987" in wrong_number["note"]
    wrong_quote = judge(f'412 gulls: "{INVENTED}" {LINK}')
    assert wrong_quote["state"] == cit.PARTIAL and "NOT found" in wrong_quote["note"]
    unjudged = judge(f'987 gulls: "{REAL}" {LINK}', cut_page(WEB))
    assert unjudged["state"] == cit.NOT_VERIFIED


def cut_page(text, why="the page came truncated"):
    page = cit.Page(text)
    page.unread = why
    return page


@pytest.mark.parametrize("quote", [REAL, INVENTED])
def test_a_page_not_read_whole_is_not_verified_and_never_says_not_found(quote):
    for page in (cut_page(WEB), WEB + "<p unfinished", WEB + "<!-- unfinished", WEB + "<script>unfinished"):
        r = judge(f'"{quote}" {LINK}', page)
        assert r["state"] == cit.NOT_VERIFIED, page[-20:]
        assert "NOT checked" in r["note"] and "NOT found" not in r["note"]


@pytest.mark.parametrize("page", ["", "<html><body></body></html>", "<p>x</p>&#" + "9" * 5000 + ";"])
def test_a_page_with_no_text_or_that_cannot_be_decoded_is_not_verified(page):
    r = judge(f'"{REAL}" {LINK}', page)
    assert r["state"] == cit.NOT_VERIFIED and "NOT found" not in r["note"]


@pytest.mark.parametrize("status,state", [
    (404, "BROKEN"), (410, "BROKEN"), (401, "NOT_VERIFIED"), (403, "NOT_VERIFIED"), (405, "NOT_VERIFIED"),
    (500, "NOT_VERIFIED"), (302, "NOT_VERIFIED"), (300, "NOT_VERIFIED"), (0, "NOT_VERIFIED"),
    (cit.REFUSED, "NOT_VERIFIED"), (200, "VERIFIED"), (203, "VERIFIED"),
])
def test_a_quote_is_only_judged_against_a_page_that_was_read(status, state):
    r = judge(f'"{REAL}" {LINK}', WEB, status)
    assert r["state"] == state and "NOT found" not in r["note"]
    if state == "NOT_VERIFIED":
        assert "quote NOT checked: the page was not read" in r["note"]
        assert (f"(status {status}" in r["note"]) is (status > 0)


def test_a_page_the_parser_chokes_on_is_still_not_verified(monkeypatch):
    def boom(*a, **k):
        raise RecursionError
    monkeypatch.setattr(cit, "visible_text", boom)
    assert judge(f'"{REAL}" {LINK}')["state"] == cit.NOT_VERIFIED


def test_a_quote_in_a_fenced_block_is_not_checked_but_the_link_still_is():
    inside = f'412 "{INVENTED}" {LINK}'
    after = f'"{INVENTED}" {LINK}'
    text = f"```\n{inside}\n~~~\n{inside}\n``` not a close\n{inside}\n````\n{after}\n  ~~~~\n```\n{inside}\n~~~\n{inside}\n~~~~~\n{after}\n"
    res = cit.check_text(text, lambda url: (200, WEB))
    assert [(r["line"], r["state"]) for r in res] == [
        (2, cit.VERIFIED), (4, cit.VERIFIED), (6, cit.VERIFIED), (8, cit.PARTIAL),
        (11, cit.VERIFIED), (13, cit.VERIFIED), (15, cit.PARTIAL)]
    assert cit.fenced_lines("a\n```py\nb\n```\nc") == {2, 3, 4}


def test_no_network_stays_the_same_with_a_quote():
    r = cit.check_one(cit.extract(f'"{REAL}" {LINK}')[0], None)
    assert (r["state"], r["note"]) == (cit.NOT_VERIFIED, "no network: the form was read, the content was not")


@pytest.mark.parametrize("quote,rc", [(REAL, 0), (INVENTED, 4)])
def test_the_rc_of_a_run_follows_the_quote(tmp_path, monkeypatch, capsys, quote, rc):
    f = tmp_path / "a.md"
    f.write_text(f'"{quote}" {LINK}\n', encoding="utf-8")
    monkeypatch.setattr(cit, "fetch_http", lambda url: (200, WEB))
    assert cit.main([str(f)]) == rc


# ---- lines without a quote behave exactly as before ----------------------------------------------

AROUND = "412: ...Harbour log The lighthouse keeper counted 412 gulls over the long winter and wrote that the north wa..."
FOUND = (cit.VERIFIED, f"every number is on the page, whole -> {AROUND}")
NO_NUMBER = (cit.NOT_VERIFIED, "opened (status 200), but the sentence claims no number to compare")


@pytest.mark.parametrize("line,status,expected", [
    (f"412 gulls {LINK}", 200, FOUND),
    (f"999 gulls {LINK}", 200, (cit.PARTIAL, "opened, but NOT found ['999'] (whole, on the page)")),
    (f"412 and 999 gulls {LINK}", 200, (cit.PARTIAL, f"found ['412'] but NOT ['999'] (whole, on the page) -> {AROUND}")),
    (f"gulls {LINK}", 200, NO_NUMBER),
    (f'412 gulls, the "winter count" of the keeper {LINK}', 200, FOUND),
    (f"412 gulls on the keeper\u2019s 13\" screen, Home \u00bb Logs {LINK}", 200,
     (cit.PARTIAL, f"found ['412'] but NOT ['13'] (whole, on the page) -> {AROUND}")),
    (f"412 gulls and `\"a quoted bit of five words\"` {LINK}", 200, FOUND),
    (f"412 gulls {LINK}", 403, (cit.PARTIAL, "answered 403 to a GET: probably a POST-only or authenticated endpoint")),
    (f"412 gulls {LINK}", 404, (cit.BROKEN, "does not exist (status 404)")),
    (f"412 gulls {LINK}", 500, (cit.NOT_VERIFIED, "answered 500: the server could not settle it, which is not proof it is gone")),
    (f"412 gulls {LINK}", 0, (cit.NOT_VERIFIED, "no answer (network down or host gone): cannot say the page is broken")),
])
def test_a_line_without_a_quote_gives_the_same_result_as_before(line, status, expected):
    for page in (WEB, cut_page(WEB)):  # and a truncated page does not change the number check
        r = judge(line, page, status)
        assert (r["state"], r["note"]) == expected
        assert set(r) == {"kind", "target", "line", "context", "state", "note"}


def test_a_404_with_a_quote_keeps_the_old_note():
    r = judge(f'"{REAL}" {LINK}', "", 404)
    assert (r["state"], r["note"]) == (cit.BROKEN, "does not exist (status 404)")


# ---- what the fetch says about the body ----------------------------------------------------------

def served(monkeypatch, raw, status=200, length=0):
    """_fetch over a scripted response: (status, body)."""
    import io

    class Response(io.BytesIO):
        pass

    r = Response(raw)
    r.status, r.length = status, length

    class Opener:
        def open(self, req, timeout):
            return r

    monkeypatch.setattr(cit, "_opener", Opener)
    return cit._fetch("https://pages.test/log")


def test_a_whole_utf8_page_is_read_as_whole(monkeypatch):
    status, body = served(monkeypatch, "caf\u00e9".encode("utf-8"))
    assert (status, body, body.unread) == (200, "caf\u00e9", "")


def test_a_page_over_the_limit_is_cut_and_says_so(monkeypatch):
    monkeypatch.setattr(cit, "MAX_BYTES", 20_000)
    _, body = served(monkeypatch, b"a" * 20_000)
    assert len(body) == 20_000 and body.unread == ""  # exactly the limit is whole
    _, body = served(monkeypatch, b"a" * 20_001)
    assert len(body) == 20_000 and "larger than" in body.unread
    _, body = served(monkeypatch, b"a" * 90_000)
    assert len(body) == 20_000 and "larger than" in body.unread
    monkeypatch.setattr(cit, "MAX_BYTES", 16_384)  # exactly one read block: the byte past it must still be asked for
    _, body = served(monkeypatch, b"a" * 16_385)
    assert len(body) == 16_384 and "larger than" in body.unread


def test_a_page_that_is_not_utf8_says_so_and_keeps_the_text_for_the_numbers(monkeypatch):
    _, body = served(monkeypatch, "caf\u00e9 412".encode("latin-1"))
    assert "412" in body and "not valid UTF-8" in body.unread
    assert judge(f'"{REAL}" {LINK}', body)["state"] == cit.NOT_VERIFIED


def test_a_partial_content_answer_is_truncated(monkeypatch):
    assert "truncated" in served(monkeypatch, b"abc", status=206)[1].unread


def test_a_body_shorter_than_declared_is_truncated():
    """The real stdlib response: a `read(n)` that hits the end early does not raise, it only leaves `length`."""
    import http.client
    import io

    class Sock:
        def makefile(self, *a, **k):
            return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nonly this")

    r = http.client.HTTPResponse(Sock())
    r.begin()

    class Opener:
        def open(self, req, timeout):
            return r

    original, cit._opener = cit._opener, Opener
    try:
        status, body = cit._fetch("https://pages.test/log")
    finally:
        cit._opener = original
    assert (status, body) == (200, "only this") and "truncated" in body.unread
