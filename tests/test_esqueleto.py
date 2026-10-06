"""O esqueleto vault/ que o usuário recebe tem que passar nos próprios verificadores."""
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VAULT = RAIZ / "vault"


def rodar(script, *args):
    return subprocess.run([sys.executable, str(RAIZ / "nucleo" / script), "--vault", str(VAULT), *args],
                          capture_output=True, text=True)


def test_estrutura_minima():
    assert (VAULT / "home.md").is_file() and (VAULT / "inbox").is_dir()
    areas = [l for l in (VAULT / "areas.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")]
    assert len(areas) == 3
    for a in areas:
        pasta = a.split(":")[0].strip()
        assert list((VAULT / "notes" / pasta).glob("*.md")), pasta


def test_portao_e_anel_passam_no_esqueleto():
    assert rodar("portao.py").returncode == 0
    assert rodar("anel.py", "--gate").returncode == 0


def test_obsidian_app_json_so_com_o_que_o_portao_pressupoe():
    cfg = VAULT / ".obsidian"
    app = json.loads((cfg / "app.json").read_text(encoding="utf-8"))
    assert app["useMarkdownLinks"] is False          # links em wikilink
    assert not (cfg / "community-plugins.json").exists() and not (cfg / "plugins").exists()
    assert sorted(p.name for p in cfg.iterdir()) == ["app.json"]
