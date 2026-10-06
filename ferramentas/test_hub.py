"""Testes em par do hub.py. HUB_PATH aponta para outra copia (usado pela mutacao)."""
import os
import subprocess
import sys
from pathlib import Path

HUB = os.environ.get("HUB_PATH") or str(Path(__file__).with_name("hub.py"))


def hub(vault, *args):
    return subprocess.run([sys.executable, HUB, "--vault", str(vault), *args],
                          capture_output=True, text=True)


def projeto(vault, nome="p", extras=()):
    d = vault / "projects" / nome
    d.mkdir(parents=True)
    (d / "instructions.md").write_text("# p\n\ntexto que sobrevive\n")
    for e in extras:
        (d / e).parent.mkdir(parents=True, exist_ok=True)
        (d / e).write_text("x")
    return d


def test_arquivo_fora_do_bloco_reprova_e_depois_passa(tmp_path):
    d = projeto(tmp_path, extras=["a.md", "sub/b.md"])
    assert hub(tmp_path, "--check").returncode == 1
    assert hub(tmp_path).returncode == 0
    assert hub(tmp_path, "--check").returncode == 0
    texto = (d / "instructions.md").read_text()
    assert "texto que sobrevive" in texto
    assert "[[projects/p/a|a]]" in texto and "[[projects/p/sub/b|b]]" in texto
    assert "[[projects/p/instructions" not in texto


def test_projeto_sem_extras_passa_sem_mexer(tmp_path):
    d = projeto(tmp_path)
    antes = (d / "instructions.md").read_text()
    assert hub(tmp_path, "--check").returncode == 0
    assert hub(tmp_path).returncode == 0
    assert (d / "instructions.md").read_text() == antes


def test_gravar_duas_vezes_deixa_um_bloco(tmp_path):
    d = projeto(tmp_path, extras=["a.md"])
    hub(tmp_path)
    hub(tmp_path)
    assert (d / "instructions.md").read_text().count("<!-- hub:inicio -->") == 1


def test_arquivo_novo_depois_do_bloco_volta_a_reprovar(tmp_path):
    d = projeto(tmp_path, extras=["a.md"])
    hub(tmp_path)
    (d / "c.md").write_text("c")
    assert hub(tmp_path, "--check").returncode == 1


def test_dry_run_nao_grava(tmp_path):
    d = projeto(tmp_path, extras=["a.md"])
    antes = (d / "instructions.md").read_text()
    r = hub(tmp_path, "--dry-run")
    assert "[[projects/p/a|a]]" in r.stdout
    assert (d / "instructions.md").read_text() == antes


def test_flag_desconhecida_recusa_sem_gravar(tmp_path):
    d = projeto(tmp_path, extras=["a.md"])
    antes = (d / "instructions.md").read_text()
    assert hub(tmp_path, "--bogus").returncode == 2
    assert (d / "instructions.md").read_text() == antes


def test_projeto_fora_do_indice_reprova(tmp_path):
    projeto(tmp_path)
    (tmp_path / "projects" / "_index.md").write_text("| outro | ativo |\n")
    assert hub(tmp_path, "--check").returncode == 1
    (tmp_path / "projects" / "_index.md").write_text("| p | ativo |\n")
    assert hub(tmp_path, "--check").returncode == 0


def test_selftest():
    assert subprocess.run([sys.executable, HUB, "--selftest"]).returncode == 0


def test_check_nao_grava(tmp_path):
    d = projeto(tmp_path, extras=["a.md"])
    antes = (d / "instructions.md").read_text()
    assert hub(tmp_path, "--check").returncode == 1
    assert (d / "instructions.md").read_text() == antes


def test_regravar_bloco_velho_troca_em_vez_de_duplicar(tmp_path):
    d = projeto(tmp_path, extras=["a.md"])
    hub(tmp_path)
    (d / "c.md").write_text("c")
    hub(tmp_path)
    texto = (d / "instructions.md").read_text()
    assert texto.count("<!-- hub:inicio -->") == 1 and "[[projects/p/c|c]]" in texto
