"""The vault/ skeleton the user receives has to pass its own checkers."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"


def run(script, *args):
    return subprocess.run([sys.executable, str(ROOT / "core" / script), "--vault", str(VAULT), *args],
                          capture_output=True, text=True)


def test_minimal_structure():
    assert (VAULT / "home.md").is_file() and (VAULT / "inbox").is_dir()
    areas = [l for l in (VAULT / "areas.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")]
    assert len(areas) == 3
    for a in areas:
        folder = a.split(":")[0].strip()
        assert list((VAULT / "notes" / folder).glob("*.md")), folder


def test_gate_and_ring_pass_on_the_skeleton():
    assert run("gate.py").returncode == 0
    assert run("ring.py", "--gate").returncode == 0


def test_obsidian_app_json_only_with_what_the_gate_assumes():
    cfg = VAULT / ".obsidian"
    app = json.loads((cfg / "app.json").read_text(encoding="utf-8"))
    assert app["useMarkdownLinks"] is False          # wikilink-style links
    assert not (cfg / "community-plugins.json").exists() and not (cfg / "plugins").exists()
    assert sorted(p.name for p in cfg.iterdir()) == ["app.json"]
