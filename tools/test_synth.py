"""Paired tests for synth.py: the same seed gives the same bytes, and the vault has the shape the scale measurements assume."""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

SYNTH = str(Path(__file__).with_name("synth.py"))
CORE = Path(__file__).resolve().parent.parent / "core"


def make(out, n=400, seed=7, *extra):
    return subprocess.run([sys.executable, SYNTH, str(out), "--notes", str(n), "--seed", str(seed), *extra], capture_output=True, text=True)


def digest(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    out = tmp_path_factory.mktemp("synth")
    assert make(out).returncode == 0
    return out / "vault"


def test_same_seed_same_bytes_other_seed_other_bytes(tmp_path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    make(a), make(b), make(c, 400, 8)
    assert digest(a) == digest(b) and digest(a) != digest(c)


def test_more_notes_means_more_files(tmp_path):
    small, big = tmp_path / "s", tmp_path / "b"
    make(small, 200), make(big, 800)
    count = lambda r: len(list((r / "vault").rglob("*.md")))
    assert 190 <= count(small) <= 230 and 790 <= count(big) <= 860


def test_the_shape_is_areas_projects_inbox_and_tasks(vault):
    areas = {p.name for p in (vault / "notes").iterdir()}
    assert len(areas) == 6 and areas <= set((vault / "areas.txt").read_text().split())
    assert len(list((vault / "inbox").glob("*.md"))) == 40 and len(list((vault / "tasks").glob("*.md"))) == 24
    assert len(list((vault / "projects").glob("*/instructions.md"))) == 4


def test_a_few_projects_hold_most_of_the_files(vault):
    sizes = sorted((len(list(p.parent.rglob("*.md"))) for p in (vault / "projects").glob("*/instructions.md")), reverse=True)
    assert sizes[0] >= 2 * sizes[-1]


def test_the_vault_passes_its_own_checkers(vault):
    for script, args in (("gate.py", []), ("ring.py", ["--gate"])):
        r = subprocess.run([sys.executable, str(CORE / script), "--vault", str(vault), *args], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-500:]
    r = subprocess.run([sys.executable, str(CORE / "leak.py"), str(vault)], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "LEAK_BLOCKLIST": str(vault / "absent.txt")})
    assert r.stdout.startswith("0 finding(s)")


def test_links_per_file_are_near_the_measured_ratio(vault):
    files = list(vault.rglob("*.md"))
    links = sum(len(re.findall(r"\[\[", p.read_text())) for p in files)
    assert 5.0 <= links / len(files) <= 9.0         # the private vault it imitates: 25069 links in 3795 files = 6.6


def test_in_degree_has_a_heavy_tail(vault):
    inbound = {}
    for p in (vault / "notes").rglob("*.md"):
        for t in re.findall(r"\[\[(notes/[^|\]]+)", p.read_text()):
            inbound[t] = inbound.get(t, 0) + 1
    values = sorted(inbound.values(), reverse=True)
    assert values[0] >= 4 * (sum(values) / len(values))


def test_about_a_sixth_of_the_notes_are_cited_by_a_project_file(vault):
    cited = set()
    for p in (vault / "projects").rglob("*.md"):
        cited |= set(re.findall(r"\[\[(notes/[^|\]]+)", p.read_text()))
    notes = len(list((vault / "notes").rglob("*.md")))
    assert 0.08 <= len(cited) / notes <= 0.25


def test_every_note_has_a_date_in_the_fixed_window_and_a_target_that_exists(vault):
    for p in list((vault / "notes").rglob("*.md"))[:50]:
        text = p.read_text()
        d = re.search(r"^date: (\d{4}-\d{2}-\d{2})$", text, re.M).group(1)
        assert "2026-04-04" <= d <= "2026-10-01"
        t = re.search(r"^target: (\S+)$", text, re.M).group(1)
        assert (vault / t).is_file()


def test_the_project_roots_carry_the_generated_list(vault):
    roots = list((vault / "projects").glob("*/instructions.md"))
    assert all("<!-- hub:start -->" in r.read_text() for r in roots)


def test_memory_grows_with_the_note_count(tmp_path):
    make(tmp_path / "s", 200), make(tmp_path / "b", 2000)
    size = lambda r: sum((r / "vault/memory" / f"{n}.md").stat().st_size for n in ("profile", "patterns", "decisions"))
    assert size(tmp_path / "b") > 5 * size(tmp_path / "s")


def test_it_refuses_a_folder_that_has_files_unless_forced(tmp_path):
    (tmp_path / "keep.txt").write_text("mine")
    r = make(tmp_path)
    assert r.returncode == 2 and "not empty" in r.stderr and (tmp_path / "keep.txt").read_text() == "mine" and not (tmp_path / "vault").exists()
    assert make(tmp_path, 100, 7, "--force").returncode == 0 and (tmp_path / "vault").is_dir()


def test_too_few_notes_is_a_usage_error(tmp_path):
    assert make(tmp_path / "x", 10).returncode == 2


def test_nothing_is_written_outside_the_given_folder(tmp_path):
    out = tmp_path / "out"
    assert make(out, 100).returncode == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out"] and sorted(p.name for p in out.iterdir()) == ["vault"]
