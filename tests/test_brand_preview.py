"""brand_preview.py: contrast math, validation and escaping, through the real CLI in a temporary folder."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "brand_preview.py"

BASE = {
    "name": "Demo",
    "colors": {"ink": "#000000", "paper": "#ffffff", "grey": "#777777", "mid": "#767676",
               "red": "#ff0000", "pale": "#cccccc"},
    "type": {"heading": "Inter", "body": "Georgia"},
    "space": [4, 8, 16],
    "radius": 6,
    "pairs": [["ink", "paper"]],
}


def run(tmp_path, data, *extra):
    (tmp_path / "tokens.json").write_text(json.dumps(data), encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), "tokens.json", *extra],
                          cwd=tmp_path, capture_output=True, text=True)


def with_pairs(*pairs):
    return {**BASE, "pairs": [list(p) for p in pairs]}


def test_black_on_white_is_21_and_aaa(tmp_path):
    r = run(tmp_path, BASE)
    assert r.returncode == 0
    assert "ink on paper: 21.00:1 AAA" in r.stdout
    assert (tmp_path / "preview.html").is_file()


def test_red_on_white_uses_the_wcag_weights(tmp_path):
    r = run(tmp_path, with_pairs(("red", "paper")))
    assert "4.00:1 fail" in r.stdout  # 3.998: fails AA by a hair
    assert r.returncode == 1


def test_aa_threshold_is_4_5(tmp_path):
    r = run(tmp_path, with_pairs(("grey", "paper")))  # 4.48:1
    assert "fail" in r.stdout and r.returncode == 1
    r = run(tmp_path, with_pairs(("mid", "paper")))  # 4.54:1
    assert "AA" in r.stdout and "AAA" not in r.stdout and r.returncode == 0


def test_aaa_threshold_is_7(tmp_path):
    r = run(tmp_path, with_pairs(("mid", "paper")))
    assert "4.54:1 AA\n" in r.stdout


def test_low_contrast_pair_fails_but_the_file_is_written(tmp_path):
    r = run(tmp_path, with_pairs(("pale", "paper")))
    assert r.returncode == 1
    assert (tmp_path / "preview.html").is_file()


def test_out_flag_chooses_the_file(tmp_path):
    r = run(tmp_path, BASE, "--out", "brand.html")
    assert r.returncode == 0 and (tmp_path / "brand.html").is_file()
    assert not (tmp_path / "preview.html").exists()


def test_html_is_self_contained(tmp_path):
    run(tmp_path, BASE)
    text = (tmp_path / "preview.html").read_text(encoding="utf-8")
    assert "<script" not in text and "http" not in text and "<link" not in text
    assert "'Inter', system-ui" in text and "'Georgia', system-ui" in text


def test_name_injection_is_escaped(tmp_path):
    run(tmp_path, {**BASE, "name": "<script>alert(1)</script>", "colors": {**BASE["colors"], "<b>x</b>": "#123456"}})
    text = (tmp_path / "preview.html").read_text(encoding="utf-8")
    assert "<script>alert" not in text and "&lt;script&gt;" in text
    assert "<b>x</b>" not in text


def test_font_name_cannot_break_out_of_css(tmp_path):
    r = run(tmp_path, {**BASE, "type": {"heading": "x'; } body { display:none", "body": "Georgia"}})
    assert r.returncode == 2
    assert "type.heading" in r.stderr


def test_no_colors_is_not_verified_and_writes_nothing(tmp_path):
    for data in ({"name": "Demo"}, {"name": "Demo", "colors": {}}):
        r = run(tmp_path, data)
        assert r.returncode == 3
        assert "NOT_VERIFIED: no colors declared" in r.stdout
        assert not (tmp_path / "preview.html").exists()


def test_invalid_hex_exits_two_and_names_the_field(tmp_path):
    for bad in ("#12345", "123456", "#12345g", "red", 5):
        r = run(tmp_path, {**BASE, "colors": {"ink": bad}})
        assert r.returncode == 2 and "colors.ink" in r.stderr
        assert not (tmp_path / "preview.html").exists()


def test_unknown_token_in_pairs_exits_two(tmp_path):
    r = run(tmp_path, with_pairs(("ink", "nope")))
    assert r.returncode == 2 and "nope" in r.stderr


def test_wrong_types_exit_two(tmp_path):
    for field, value in (("space", "4"), ("space", [True]), ("radius", "6"), ("pairs", [["ink"]]), ("name", 3)):
        assert run(tmp_path, {**BASE, field: value}).returncode == 2, field


def test_invalid_json_exits_two(tmp_path):
    (tmp_path / "tokens.json").write_text("{not json", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "tokens.json"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 2


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "SELFTEST OK" in r.stdout


def test_no_pairs_is_not_verified_but_still_writes_the_file(tmp_path):
    r = run(tmp_path, {k: v for k, v in BASE.items() if k != "pairs"})
    assert r.returncode == 3, r.stdout + r.stderr
    assert "NOT_VERIFIED: no pairs declared" in r.stdout
    assert (tmp_path / "preview.html").is_file()
