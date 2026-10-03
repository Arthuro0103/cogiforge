"""anel.py: nota sem nenhum wikilink de entrada ou saída é órfã; inbox é isento; o gate ensina."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import anel
from helpers import vault

SCRIPT = Path(__file__).resolve().parent.parent / "nucleo" / "anel.py"
PAR = {"a.md": "vai para [[b]]\n", "b.md": "volta para [[a]]\n"}


def orfas(tmp_path, arquivos):
    v = vault(tmp_path, {**PAR, **arquivos})
    arqs, deg = anel.analisar(v)
    return anel.chk_orfas(arqs, deg)


def test_nota_ligada_nao_e_orfa(tmp_path):
    assert orfas(tmp_path, {}) == []


def test_nota_sem_nenhum_link_e_orfa(tmp_path):
    assert orfas(tmp_path, {"solta.md": "nada aqui\n"}) == ["solta.md"]


def test_so_link_de_saida_ou_so_de_entrada_basta(tmp_path):
    assert orfas(tmp_path, {"sai.md": "vai [[a]]\n", "a2.md": "x\n", "a.md": "vai [[b]] e [[a2]]\n"}) == []


def test_link_morto_nao_e_aresta(tmp_path):
    assert orfas(tmp_path, {"so-morto.md": "[[nao-existe]]\n"}) == ["so-morto.md"]


def test_autolink_nao_e_aresta(tmp_path):
    assert orfas(tmp_path, {"eu.md": "[[eu]]\n"}) == ["eu.md"]


def test_link_em_codigo_nao_e_aresta(tmp_path):
    assert orfas(tmp_path, {"c.md": "```\n[[a]]\n```\n`[[b]]`\n"}) == ["c.md"]


def test_link_markdown_comum_e_aresta(tmp_path):
    assert orfas(tmp_path, {"m.md": "veja [a](a.md)\n"}) == []


def test_link_markdown_com_espaco_codificado_resolve(tmp_path):
    v = vault(tmp_path, {"m.md": "veja [x](sub%20dir/x.md)\n", "sub dir/x.md": "x\n"})
    arqs, deg = anel.analisar(v)
    assert anel.chk_orfas(arqs, deg) == []


def test_link_pra_imagem_nao_e_aresta(tmp_path):
    assert orfas(tmp_path, {"img.png": "x", "i.md": "![[img.png]]\n"}) == ["i.md"]


def test_inbox_e_isento_mas_nao_e_dado_como_ligado(tmp_path):
    assert orfas(tmp_path, {"inbox/captura.md": "ideia solta\n"}) == []
    v = vault(tmp_path / "x", {**PAR, "inbox/captura.md": "ideia solta\n"})
    arqs, deg = anel.analisar(v)
    assert deg["inbox/captura.md"] == 0


def test_link_vindo_do_inbox_conta_como_aresta(tmp_path):
    assert orfas(tmp_path, {"destino.md": "x\n", "inbox/c.md": "vai [[destino]]\n"}) == []


def test_fora_do_inbox_com_nome_parecido_nao_e_isento(tmp_path):
    assert orfas(tmp_path, {"inbox-velho/x.md": "x\n", "notas/inbox/y.md": "y\n"}) == [
        "inbox-velho/x.md", "notas/inbox/y.md"]


# ---- gate --------------------------------------------------------------------

def gate(v, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--gate", *args],
                          capture_output=True, text=True)


def test_gate_reprova_orfa_e_ensina_o_conserto(tmp_path):
    v = vault(tmp_path, {**PAR, "solta.md": "nada\n"})
    r = gate(v)
    assert r.returncode == 1 and "solta.md" in r.stdout
    for dica in ("Como consertar", "[[", "inbox/", "--no-verify"):
        assert dica in r.stdout


def test_gate_cura_e_passa(tmp_path):
    v = vault(tmp_path, {**PAR, "solta.md": "nada\n"})
    assert gate(v).returncode == 1
    (v / "solta.md").write_text("agora liga com [[a]]\n", encoding="utf-8")
    assert gate(v).returncode == 0


def test_gate_vault_inexistente_nao_diz_ok(tmp_path):
    r = gate(tmp_path / "nao-existe")
    assert r.returncode == 2 and "OK" not in r.stdout


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


def test_stage_so_reprova_o_que_esta_no_commit(tmp_path):
    v = vault(tmp_path, {**PAR, "no-commit.md": "x\n", "fora.md": "y\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "no-commit.md")
    r = gate(v, "--stage")
    assert r.returncode == 1 and "no-commit.md" in r.stdout
    assert "AVISO" in r.stdout and "fora.md" in r.stdout
    git(tmp_path, "reset", "-q")
    git(tmp_path, "add", "a.md")
    r = gate(v, "--stage")
    assert r.returncode == 0 and "AVISO" in r.stdout and "fora.md" in r.stdout


def test_stage_funciona_com_vault_numa_subpasta_e_acento(tmp_path):
    v = vault(tmp_path / "vault", {**PAR, "notas/ação.md": "x\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "vault/notas/ação.md")
    assert gate(v, "--stage").returncode == 1


def test_stage_fora_de_repo_git_e_nao_verificado_nunca_ok(tmp_path):
    v = vault(tmp_path, {**PAR, "solta.md": "x\n"})
    r = gate(v, "--stage")
    assert r.returncode == 2 and "NAO_VERIFICADO" in r.stdout


def test_cli_json(tmp_path):
    v = vault(tmp_path, {**PAR, "solta.md": "x\n", "inbox/i.md": "y\n"})
    d = json.loads(subprocess.run([sys.executable, str(SCRIPT), "--vault", str(v), "--json"],
                                  capture_output=True, text=True).stdout)
    assert d == {"total": 4, "orfas": ["solta.md"], "isentas": ["inbox/i.md"]}


def test_selftest_passa():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0 and "SELFTEST OK" in r.stdout


def test_aresta_vai_pra_nota_da_mesma_pasta_e_a_outra_continua_orfa(tmp_path):
    v = vault(tmp_path, {"x/a.md": "vai [[b]]\n", "x/b.md": "x\n", "y/b.md": "y\n"})
    arqs, deg = anel.analisar(v)
    assert anel.chk_orfas(arqs, deg) == ["y/b.md"]


def test_stage_com_nome_em_nfd_casa_com_o_que_o_git_devolve(tmp_path):
    import unicodedata
    nome = unicodedata.normalize("NFD", "ação.md")
    v = vault(tmp_path, {**PAR, nome: "x\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", nome)
    assert gate(v, "--stage").returncode == 1


def test_selftest_reprova_quando_o_gate_mente(monkeypatch, capsys):
    monkeypatch.setattr(anel, "gate", lambda *a, **k: 0)   # um gate que sempre diz OK
    assert anel.selftest() == 1
    assert "FALHOU" in capsys.readouterr().out
