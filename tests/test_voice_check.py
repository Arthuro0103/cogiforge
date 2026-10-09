"""voice_check.py: every rule kind gets a pair (text that trips it + plausible text that passes).

Runs the real CLI in a temporary folder. A rule that touches nothing is NOT_VERIFIED (rc 3), never OK.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "voice_check.py"

VOICE = """---
type: voice
scope: person
---
## Phrases
- 2026-01-01 | "keep it plain"
## Never say
- synergy
- game changer
- <term>
-
<!-- - hidden -->
## Avoid
- art
- leverage
## Pairs
- say: "use" | not: "utilize"
"""


def run(tmp_path, text, voice=VOICE, *extra):
    (tmp_path / "t.md").write_text(text, encoding="utf-8")
    argv = [sys.executable, str(SCRIPT), "t.md", "--vault", "vault", *extra]
    if voice is not None:
        (tmp_path / "v.md").write_text(voice, encoding="utf-8")
        argv += ["--person", "v.md"]
    return subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True)


def test_clean_text_exits_zero(tmp_path):
    r = run(tmp_path, "A plain sentence about the product.\n")
    assert r.returncode == 0
    assert r.stdout.count("OK:") == 1


def test_never_say_is_found_with_file_line_and_kind(tmp_path):
    r = run(tmp_path, "fine\nour synergy is here\n")
    assert r.returncode == 1
    assert "t.md:2: [never] synergy" in r.stdout


def test_avoid_is_found_and_labelled(tmp_path):
    r = run(tmp_path, "we leverage it\n")
    assert r.returncode == 1
    assert "t.md:1: [avoid] leverage" in r.stdout


def test_output_never_echoes_the_line(tmp_path):
    r = run(tmp_path, "the secret-token-xyz and synergy\n")
    assert r.returncode == 1
    assert "secret-token-xyz" not in r.stdout + r.stderr


def test_case_is_ignored(tmp_path):
    assert run(tmp_path, "SyNeRgY\n").returncode == 1


def test_nfkc_full_width_matches(tmp_path):
    assert run(tmp_path, "ｓｙｎｅｒｇｙ\n").returncode == 1


def test_expression_matches_across_extra_spaces(tmp_path):
    assert run(tmp_path, "a real game   changer\n").returncode == 1


def test_word_inside_another_word_does_not_count(tmp_path):
    r = run(tmp_path, "let us start, it is a smart party\n")
    assert r.returncode == 0


def test_term_in_a_fenced_code_block_does_not_count(tmp_path):
    r = run(tmp_path, "clean\n```\nsynergy\n```\nclean again\n")
    assert r.returncode == 0


def test_term_in_the_text_frontmatter_does_not_count(tmp_path):
    r = run(tmp_path, "---\ntitle: synergy\n---\nclean\n")
    assert r.returncode == 0


def test_rule_that_touches_nothing_is_not_verified(tmp_path):
    """Placeholders and empty items are not rules: the check never ran, so it cannot say OK."""
    empty = "## Never say\n- <term>\n-\n<!-- - hidden -->\n## Avoid\n- <another>\n"
    r = run(tmp_path, "text with <term> and hidden inside\n", empty)
    assert r.returncode == 3
    assert "NOT_VERIFIED" in r.stdout
    assert "OK" not in r.stdout.replace("NOT_VERIFIED", "")


def test_no_voice_file_is_not_verified(tmp_path):
    r = run(tmp_path, "hello\n", None)
    assert r.returncode == 3
    assert "NOT_VERIFIED" in r.stdout


def test_text_with_only_code_is_not_verified(tmp_path):
    r = run(tmp_path, "```\nsynergy\n```\n")
    assert r.returncode == 3


def test_missing_text_file_exits_two(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "absent.md"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 2


def test_missing_explicit_person_file_exits_two(tmp_path):
    (tmp_path / "t.md").write_text("hello\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "t.md", "--person", "nope.md"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 2


def test_project_rules_add_to_person_rules(tmp_path):
    brand = tmp_path / "vault" / "projects" / "demo" / "brand"
    brand.mkdir(parents=True)
    (brand / "voice.md").write_text("## Never say\n- bespoke\n", encoding="utf-8")
    r = run(tmp_path, "a bespoke thing\n", VOICE, "--project", "demo")
    assert r.returncode == 1 and "[never] bespoke" in r.stdout
    r = run(tmp_path, "a bespoke thing\n", VOICE)  # without --project the project file is not read
    assert r.returncode == 0


def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "SELFTEST OK" in r.stdout
