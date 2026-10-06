"""The template's gate gives the SAME verdict as the Brain's, on the checks both have.

The Brain is the author's private vault and still speaks Portuguese. So the demo is translated back to
Portuguese first (folders, areas, the `target:` key, link paths, file names), using the table in
docs/TRANSLATING.md, the Brain's script runs on that copy, and its answer is translated forward again to
compare. The table is the single source: if a name changes here but not there, this test notices.

The Brain pins the VAULT by the script's own path (`parent.parent`), so its script is copied to
<tmp>/scripts/ and the translated demo to <tmp>/. Without the Brain (public CI), the test is SKIPPED
and prova.yml prints NOT_VERIFIED: skipping is not passing.

    COGIFORGE_BRAIN=/path/to/Brain pytest tests/test_equivalence.py -rs

Checks in common (template names): frontmatter, area, dead-link, broken-link, dead-target. Left out, on purpose:
titulo, caminho-morto and sem-link-no-corpo (they only exist in the Brain). What the comparison covers is what
demo/ exercises: it says "same verdict on these 15 notes", not "same behavior on everything".
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import gate

ROOT = Path(__file__).resolve().parent.parent
IN_COMMON = ["frontmatter", "area", "dead-link", "broken-link", "dead-target"]
# the Brain's own names for the checks and for the fields of its JSON answer
BRAIN_CHECK = {"dead-link": "link-morto", "broken-link": "link-partido", "dead-target": "alvo-morto"}


def names():
    """{en: pt} from the table between the markers in docs/TRANSLATING.md."""
    text = (ROOT / "docs" / "TRANSLATING.md").read_text(encoding="utf-8")
    block = text.split("<!-- names:start -->")[1].split("<!-- names:end -->")[0]
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in block.splitlines()
            if line.strip().startswith("|")]
    return {r[0]: r[1] for r in rows[2:]}  # rows[0] is the header, rows[1] the separator


def to_pt(path_like, table):
    """Translate each segment of a path or a link target; keep the extension and any #anchor or |alias.

    The lookup ignores case (a link may be written `[[CONTROL-B]]`), and the translation keeps the case style."""
    out = []
    for seg in path_like.split("/"):
        stem, dot, ext = seg.partition(".")
        pt = table.get(stem.lower(), stem)
        out.append((pt.upper() if stem.isupper() and pt != stem else pt) + dot + ext)
    return "/".join(out)


def translate_text_to_pt(text, table):
    """Frontmatter values and link targets back to Portuguese. Prose is left as it is."""
    lines, in_fm = text.split("\n"), False
    for i, line in enumerate(lines):
        if i == 0 and line == "---":
            in_fm = True
            continue
        if in_fm and line == "---":
            in_fm = False
            continue
        if in_fm:
            key, sep, val = line.partition(":")
            if key == "area":
                lines[i] = key + sep + " " + table.get(val.strip(), val.strip())
            elif key == "target":
                val = re.sub(r"[^\s,\[\]\"']+", lambda m: table.get(m.group(0), to_pt(m.group(0), table)), val)
                lines[i] = "alvo" + sep + val
    text = "\n".join(lines)
    text = re.sub(r"\[\[([^\]|#]+)", lambda m: "[[" + to_pt(m.group(1), table), text)
    return re.sub(r"\]\(([^)#]+)", lambda m: "](" + to_pt(m.group(1), table), text)


def to_en(path, table):
    back = {v: k for k, v in table.items()}
    return "/".join(back.get(seg.partition(".")[0], seg.partition(".")[0]) + seg.partition(".")[1] + seg.partition(".")[2]
                    for seg in path.split("/"))


def brain():
    b = os.environ.get("COGIFORGE_BRAIN")
    if not b or not (Path(b) / "scripts" / "portao.py").is_file():
        pytest.skip("brain absent")
    return Path(b)


def brain_verdict(b, tmp):
    table = names()
    (tmp / "scripts").mkdir(parents=True)
    for name in ("portao.py", "check_title.py"):
        if (b / "scripts" / name).is_file():
            shutil.copy(b / "scripts" / name, tmp / "scripts" / name)
    # the Brain only looks at area inside <VAULT>/notas: the translated demo becomes the VAULT itself
    for src in (ROOT / "demo").rglob("*"):
        if src.is_dir() or src.name == "areas.txt":
            continue
        dest = tmp / to_pt(src.relative_to(ROOT / "demo").as_posix(), table)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".md":
            dest.write_text(translate_text_to_pt(src.read_text(encoding="utf-8"), table), encoding="utf-8")
        else:
            shutil.copy(src, dest)
    cmd = [sys.executable, str(tmp / "scripts" / "portao.py"), "--auditar", ".", "--json"]
    for c in IN_COMMON:
        cmd += ["--check", BRAIN_CHECK.get(c, c)]
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode in (0, 1), r.stdout + r.stderr
    back = {v: k for k, v in BRAIN_CHECK.items()}
    return sorted((to_en(f["arquivo"], table), back.get(f["check"], f["check"]))
                  for f in json.loads(r.stdout)["falhas"])


def template_verdict():
    _, failures = gate.audit(ROOT / "demo", checks=set(IN_COMMON))
    return sorted((f.file, f.check) for f in failures)


def test_the_names_table_is_readable_and_complete():
    """Runs without the Brain: the table has to cover every folder, area and fixture the demo uses."""
    table = names()
    for en in ("notes", "tasks", "projects", "memory", "learning", "technology", "life", "target", "none",
               "dead-link", "broken-link", "dead-target", "orphan", "leaked", "home"):
        assert en in table, en
    for path in (ROOT / "demo").rglob("*.md"):
        stem = path.stem
        assert stem in table or stem == "home", f"{stem} is in demo/ but not in docs/TRANSLATING.md"


def test_the_demo_translates_to_portuguese_and_back():
    """Runs without the Brain: the translation must be reversible, or the comparison below proves nothing."""
    table = names()
    for path in (ROOT / "demo").rglob("*.md"):
        rel = path.relative_to(ROOT / "demo").as_posix()
        assert to_en(to_pt(rel, table), table) == rel


def test_same_verdict_on_the_checks_in_common(tmp_path):
    b = brain()
    from_brain, from_template = brain_verdict(b, tmp_path), template_verdict()
    assert from_template == from_brain


def test_the_comparison_is_not_empty(tmp_path):
    """An equivalence over zero failures would be vacuous: each check in common has to fail something."""
    b = brain()
    seen = {c for _, c in brain_verdict(b, tmp_path)}
    assert seen == set(IN_COMMON)
