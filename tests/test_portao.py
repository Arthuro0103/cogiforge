"""portao.py: cada check tem um par (reprova / passa) e os limites do parser estão fixados."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import portao
from helpers import nota, vault

SCRIPT = Path(__file__).resolve().parent.parent / "nucleo" / "portao.py"


def checks_de(tmp_path, arquivos, **kw):
    v = vault(tmp_path, arquivos)
    _, falhas = portao.auditar(v, **kw)
    return sorted((f.arquivo, f.check) for f in falhas)


# ---- frontmatter -------------------------------------------------------------

@pytest.mark.parametrize("fm", [
    "obra: Peak: Secrets from the Science",   # dois-pontos sem aspas
    "titulo: 'sem fechar",                    # aspas abertas
    "tags: [a, b",                            # lista inline aberta
    "autor:\n  nome: x",                      # mapa aninhado: fora do subconjunto
    "chave sem dois pontos",
    "desc: |", "desc: >", "ref: &ancora", "ref: *ancora", "tipo: !tag", "x: {a: b}",
    "a: valor\n  - item",   # item de lista sobre um valor que não é lista
    "\tarea: x",                              # tabulação
    "tags:\n \t- a",                          # tabulação no meio da indentação de um item
])
def test_frontmatter_invalido_reprova(tmp_path, fm):
    r = checks_de(tmp_path, {"x.md": f"---\n{fm}\n---\ncorpo\n"})
    assert r == [("x.md", "frontmatter")]


@pytest.mark.parametrize("fm", [
    "titulo: Texto simples", "titulo: \"com: dois-pontos entre aspas\"", "titulo: 'aspas simples'",
    "tags: [a, b, \"c d\"]", "tags:\n  - a\n  - b", "# comentário\nvazio:\nurl: https://x.org/a",
    "feito: sim  # comentário no fim", "lista: []",
])
def test_frontmatter_valido_passa(tmp_path, fm):
    assert checks_de(tmp_path, {"x.md": f"---\n{fm}\n---\ncorpo\n"}) == []


def test_sem_frontmatter_passa_e_frontmatter_aberto_reprova(tmp_path):
    r = checks_de(tmp_path, {"a.md": "só corpo\n", "b.md": "---\narea: x\nnunca fecha\n"})
    assert r == [("b.md", "frontmatter")]


def test_parser_devolve_tipos():
    d, erro = portao.parse_fm(["a: x", "b: [1, 'y']", "c:", "  - i", "  - j", "d:"])
    assert erro is None and d == {"a": "x", "b": ["1", "y"], "c": ["i", "j"], "d": None}


# ---- area --------------------------------------------------------------------

def test_area_ok_passa(tmp_path):
    assert checks_de(tmp_path, {"notes/life/a.md": nota("life")}) == []


@pytest.mark.parametrize("arquivos, motivo", [
    ({"notes/life/a.md": nota("technology")}, "mora em notes/technology"),   # pasta ≠ area
    ({"notes/life/a.md": "---\ntitulo: x\n---\n"}, "sem campo area"),
    ({"notes/life/a.md": nota("inventada")}, "não está na lista"),
    ({"notes/a.md": nota("life")}, "solta na raiz"),
    ({"notes/outra/a.md": nota("life")}, "nenhuma área configurada"),
])
def test_area_errada_reprova(tmp_path, arquivos, motivo):
    v = vault(tmp_path, arquivos)
    _, falhas = portao.auditar(v)
    assert [f.check for f in falhas] == ["area"] and motivo in falhas[0].msg


def test_area_fora_de_notas_nao_se_aplica(tmp_path):
    assert checks_de(tmp_path, {"inbox/a.md": "x\n", "projects/a.md": nota("qualquer")}) == []


def test_area_nao_conta_duas_vezes_quando_frontmatter_ja_reprovou(tmp_path):
    r = checks_de(tmp_path, {"notes/life/a.md": "---\nobra: A: B\n---\n"})
    assert r == [("notes/life/a.md", "frontmatter")]


def test_areas_configuraveis_por_arquivo(tmp_path):
    arq = {"areas.txt": "# minhas\nestudo\ntrabalho: emprego\n", "notes/estudo/a.md": nota("estudo"),
           "notes/trabalho/b.md": nota("emprego"), "notes/life/c.md": nota("life")}
    assert checks_de(tmp_path, arq) == [("notes/life/c.md", "area")]


# ---- link-morto --------------------------------------------------------------

@pytest.mark.parametrize("link", [
    "[[b]]", "[[b|alias]]", "[[b#secao]]", "[[B]]", "![[b]]", "[[notes/life/b]]", "[[notes/life/b.md]]",
    "[[../life/b]]", "[[life/b]]",
])
def test_link_vivo_passa(tmp_path, link):
    arq = {"notes/life/a.md": nota("life", f"{link}\n"), "notes/life/b.md": nota("life")}
    assert checks_de(tmp_path, arq) == []


@pytest.mark.parametrize("link", ["[[nao-existe]]", "[[b-quase]]", "[[outra/pasta/b]]", "[[b.png]]"])
def test_link_morto_reprova(tmp_path, link):
    arq = {"notes/life/a.md": nota("life", f"{link}\n"), "notes/life/b.md": nota("life")}
    assert checks_de(tmp_path, arq) == [("notes/life/a.md", "link-morto")]


def test_link_em_codigo_nao_e_link(tmp_path):
    corpo = "```\n[[morto-na-cerca]]\n```\n`[[morto-inline]]`\n~~~~\n```\n[[ainda-cerca]]\n~~~~\n"
    assert checks_de(tmp_path, {"a.md": corpo}) == []


def test_ancora_do_proprio_arquivo_nao_conta(tmp_path):
    assert checks_de(tmp_path, {"a.md": "[[#secao]] e [[^bloco]]\n"}) == []


def test_conta_cada_ocorrencia(tmp_path):
    v = vault(tmp_path, {"a.md": "[[x1]] [[x2]]\n[[x3]]\n"})
    _, falhas = portao.auditar(v)
    assert len(falhas) == 3


# ---- link-partido ------------------------------------------------------------

def test_link_partido_reprova(tmp_path):
    r = checks_de(tmp_path, {"a.md": "veja [[nota com nome\nlongo]] aqui\n"})
    assert r == [("a.md", "link-partido")]


def test_link_partido_nao_vira_link_morto_e_conta_por_linha(tmp_path):
    v = vault(tmp_path, {"a.md": "[[um\nlink]]\n[[dois\nlink]]\n"})
    _, falhas = portao.auditar(v)
    assert [f.check for f in falhas] == ["link-partido", "link-partido"]


def test_link_inteiro_e_codigo_passam(tmp_path):
    corpo = "[[b]] e [[b]] na mesma linha\n```\n[[partido\n```\n`[[solto`\n"
    assert checks_de(tmp_path, {"a.md": corpo, "b.md": "x\n"}) == []


# ---- alvo-morto --------------------------------------------------------------

def test_alvo_existente_passa(tmp_path):
    arq = {"a.md": "---\ntarget: x/b.md\n---\n", "x/b.md": "b\n", "c.md": "---\ntarget: x/b\n---\n"}
    assert checks_de(tmp_path, arq) == []


def test_alvo_inexistente_reprova(tmp_path):
    assert checks_de(tmp_path, {"a.md": "---\ntarget: x/some.md\n---\n"}) == [("a.md", "alvo-morto")]


def test_alvo_so_casa_por_basename_com_caminho_declarado_reprova(tmp_path):
    arq = {"a.md": "---\ntarget: pasta-errada/b.md\n---\n", "x/b.md": "b\n"}
    assert checks_de(tmp_path, arq) == [("a.md", "alvo-morto")]


def test_alvo_sem_barra_resolve_por_nome(tmp_path):
    assert checks_de(tmp_path, {"a.md": "---\ntarget: b\n---\n", "x/b.md": "b\n"}) == []


def test_alvo_lista_nenhum_diretorio_e_absoluto(tmp_path):
    d = tmp_path / "fora"
    d.mkdir()
    arq = {"a.md": f"---\ntarget: [none, x, '{d}']\n---\n", "x/b.md": "b\n"}
    assert checks_de(tmp_path / "v", arq) == []


def test_alvo_na_lista_conta_so_o_morto(tmp_path):
    arq = {"a.md": "---\ntarget: [x/b.md, x/morto.md]\n---\n", "x/b.md": "b\n"}
    v = vault(tmp_path, arq)
    _, falhas = portao.auditar(v)
    assert [(f.arquivo, f.check) for f in falhas] == [("a.md", "alvo-morto")]


# ---- CLI ---------------------------------------------------------------------

def rodar(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_cli_rc_json_e_filtro(tmp_path):
    v = vault(tmp_path, {"a.md": "[[morto]]\n", "b.md": "[[partido\nx]]\n", "c.md": "ok\n"})
    r = rodar("--vault", str(v), "--json")
    d = json.loads(r.stdout)
    assert r.returncode == 1 and d["arquivos"] == 3 and d["reprovadas"] == 2
    assert d["checagens"]["link-morto"]["notas"] == 1 and d["checagens"]["link-partido"]["ocorrencias"] == 1
    so = json.loads(rodar("--vault", str(v), "--json", "--check", "link-morto").stdout)
    assert [f["check"] for f in so["falhas"]] == ["link-morto"]


def test_cli_limpo_sai_zero(tmp_path):
    v = vault(tmp_path, {"a.md": "[[b]]\n", "b.md": "[[a]]\n"})
    assert rodar("--vault", str(v)).returncode == 0


def test_cli_vault_inexistente_sai_2(tmp_path):
    assert rodar("--vault", str(tmp_path / "nao-existe")).returncode == 2


def test_arquivo_fora_do_vault_sai_2_nunca_limpo_e_sem_traceback(tmp_path):
    """Um rascunho FORA do vault não pode ser dado como conferido: o portão resolve link e área
    relativos ao vault, então conferir o que está fora dele seria um OK que não tocou em nada.
    Achado em 03/10 ao escrever o README: o portão derrubava com traceback (rc 1, ValueError)."""
    v = vault(tmp_path / "v", {"notes/life/a.md": nota("life", "[[b]]\n"), "notes/life/b.md": nota("life", "[[a]]\n")})
    rascunho = tmp_path / "rascunho.md"  # irmão do vault, não dentro dele
    rascunho.write_text("---\narea: nada-a-ver\n---\n# Rascunho\n\nTexto.\n")
    r = rodar("--vault", str(v), str(rascunho))
    assert r.returncode == 2
    assert "fora" in r.stderr and "Traceback" not in r.stderr and "Traceback" not in r.stdout


TAREFA_COM_TEMPO = ("---\ntags:\n  - task\ntitle: Comprar pilhas\nstatus: open\ntimeEntries:\n"
                    "  - startTime: 2026-10-03T10:00:00-03:00\n    endTime: 2026-10-03T10:20:00-03:00\n---\n")  # o que o TaskNotes grava quando se registra tempo


def test_frontmatter_de_tarefa_do_plugin_nao_e_julgado_pelo_subconjunto(tmp_path):
    """tasks/ pertence ao plugin TaskNotes, cujo YAML (lista de mapas em timeEntries) é válido mas
    fica fora do subconjunto do portão. Achado em 03/10 medindo uma tarefa com tempo registrado."""
    assert checks_de(tmp_path, {"tasks/t.md": TAREFA_COM_TEMPO}) == []


def test_o_mesmo_yaml_fora_de_tarefas_continua_reprovando(tmp_path):
    assert checks_de(tmp_path, {"notes/life/t.md": TAREFA_COM_TEMPO}) == [("notes/life/t.md", "frontmatter")]


def test_link_morto_dentro_da_tarefa_ainda_reprova(tmp_path):
    tarefa = "---\ntags:\n  - task\nprojects:\n  - \"[[projects/nao-existe/instructions]]\"\n---\n"
    assert checks_de(tmp_path, {"tasks/t.md": tarefa}) == [("tasks/t.md", "link-morto")]


def test_cli_arquivo_ilegivel_sai_3_nunca_limpo(tmp_path):
    v = vault(tmp_path, {"a.md": "limpo\n"})
    (v / "a.md").chmod(0)
    try:
        r = rodar("--vault", str(v))
    finally:
        (v / "a.md").chmod(0o644)
    assert r.returncode == 3 and "ILEGIVEL" in r.stdout


def test_cli_check_desconhecido_sai_2(tmp_path):
    assert rodar("--vault", str(vault(tmp_path, {"a.md": "x\n"})), "--check", "inventado").returncode == 2


# ---- limites que a mutação cobrou ---------------------------------------------

def test_comentario_no_fim_do_valor_com_dois_pontos_passa(tmp_path):
    assert checks_de(tmp_path, {"x.md": "---\ntitulo: valor  # obs: ok\n---\n"}) == []


def test_alvo_com_caminho_declarado_so_vale_a_partir_da_raiz(tmp_path):
    arq = {"a.md": "---\ntarget: life/b.md\n---\n", "notes/life/b.md": nota("life")}
    assert checks_de(tmp_path, arq) == [("a.md", "alvo-morto")]


def test_frontmatter_com_crlf_passa(tmp_path):
    v = vault(tmp_path, {})
    (v / "x.md").write_bytes(b"---\r\narea: life\r\n---\r\ncorpo [[x]]\r\n")
    assert portao.auditar(v)[1] == []


def test_pastas_de_ferramenta_nao_sao_varridas_nem_indexadas(tmp_path):
    arq = {".obsidian/x.md": "[[morto]]\n", ".git/y.md": "[[morto]]\n", "a.md": "[[x]]\n"}
    assert checks_de(tmp_path, arq) == [("a.md", "link-morto")]  # `x` só existe em .obsidian: não conta


def test_nome_puro_acha_a_nota_da_mesma_pasta_e_senao_qualquer_uma(tmp_path):
    v = vault(tmp_path, {"x/a.md": "x\n", "x/b.md": "x\n", "y/b.md": "y\n", "z/c.md": "z\n"})
    idx = portao.Indice(v)
    assert idx.achar("b", "x/a.md") == "x/b.md" and idx.achar("b", "y/c.md") == "y/b.md"
    assert idx.achar("b", "z/c.md") in ("x/b.md", "y/b.md")


def test_ilegivel_e_arquivo_nao_utf8_nunca_e_limpo(tmp_path):
    v = vault(tmp_path, {})
    (v / "x.md").write_bytes(b"\xff\xfe\xfa lixo")
    assert [f.check for f in portao.auditar(v)[1]] == ["ILEGIVEL"]
    assert rodar("--vault", str(v)).returncode == 3
