"""vazamento.py: every check gets a pair (input that leaks + plausible input that passes).

Leaky strings are assembled at runtime so this file itself never trips the scanner.
"""
import subprocess
import sys
from pathlib import Path

import pytest

import vazamento as v

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "nucleo" / "vazamento.py"

CAMINHO = "/Users/" + "fulano"
EMAIL = "fulano" + "@" + "empresa.com.br"
CPF = "123.456.789-" + "09"
TEL_PAREN = "(11) 9" + "8765-4321"
TEL_MAIS = "+55 21 9" + "8765-4321"
TEL_NU = "11 9" + "8765-4321"


# ---- pares: vaza / passa ---------------------------------------------------

@pytest.mark.parametrize("linha", [f"abra {CAMINHO}/docs/x.md", f"cd {CAMINHO}"])
def test_caminho_vaza(linha):
    assert v.chk_caminho(linha)


@pytest.mark.parametrize("linha", [
    "a pasta /Users do macOS", "veja ~/www/projeto", "/Users/<nome>/docs", "/usr/local/bin",
])
def test_caminho_plausivel_passa(linha):
    assert v.chk_caminho(linha) == []


def test_email_vaza():
    assert v.chk_email(f"fale com {EMAIL} hoje")


@pytest.mark.parametrize("linha", [
    "escreva para fulano@example.com", "git clone git@github.com:org/repo.git",
    "use @mencao no texto", "preço 10@5 reais",
])
def test_email_plausivel_passa(linha):
    assert v.chk_email(linha) == []


@pytest.mark.parametrize("linha", [f"ligue {TEL_PAREN}", f"zap {TEL_MAIS}", f"tel {TEL_NU}"])
def test_telefone_vaza(linha):
    assert v.chk_telefone(linha)


@pytest.mark.parametrize("linha", [
    "timestamp 1759500000", "data 2026-10-03", "python 3.10-3.13", "versão 1234-5678 do manual",
])
def test_telefone_plausivel_passa(linha):
    assert v.chk_telefone(linha) == []


def test_cpf_vaza():
    assert v.chk_cpf(f"cpf {CPF}")


@pytest.mark.parametrize("linha", ["12345678909", "1.2.3", "ip 192.168.100.200-1"])
def test_cpf_plausivel_passa(linha):
    assert v.chk_cpf(linha) == []


def test_lista_vaza_sem_olhar_caixa():
    assert v.chk_lista("o Projeto Zeta-Quux está aqui", ["zeta-quux"])
    assert v.chk_lista("ZETA-QUUX", ["zeta-quux"])


def test_lista_plausivel_passa():
    assert v.chk_lista("nada de especial aqui", ["zeta-quux", "outro termo"]) == []
    assert v.chk_lista("qualquer coisa", []) == []


# ---- lista negra: leitura, ausência, arquivo fora ---------------------------

def test_ler_negra_ignora_vazias_e_comentarios(tmp_path):
    f = tmp_path / "negra.txt"
    f.write_text("# comentário\nzeta-quux\n\n  Outro Termo  \n", encoding="utf-8")
    assert v.ler_negra(f) == ["zeta-quux", "outro termo"]


def test_ler_negra_ausente_devolve_none(tmp_path):
    assert v.ler_negra(tmp_path / "nao-existe.txt") is None


# ---- varredura de ponta a ponta (processo de verdade) -----------------------

def rodar(args, cwd, negra=None):
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "VAZAMENTO_NEGRA": str(negra or cwd / "ausente.txt")}
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=env,
                          capture_output=True, text=True)


def test_varredura_acha_e_conta_linhas(tmp_path):
    (tmp_path / "ruim.md").write_text(f"ok\nvazou {CAMINHO}/x\nok\nmail {EMAIL}\n", encoding="utf-8")
    (tmp_path / "bom.md").write_text("texto limpo\nsem nada\n", encoding="utf-8")
    r = rodar(["."], tmp_path)
    achados = [l for l in r.stdout.splitlines() if l.startswith("ruim.md:")]
    assert r.returncode == 1
    assert len(achados) == 2 and "bom.md" not in r.stdout


def test_varredura_limpa_sai_zero(tmp_path):
    (tmp_path / "bom.md").write_text("texto limpo\n", encoding="utf-8")
    assert rodar(["."], tmp_path).returncode == 0


def test_sem_lista_privada_diz_nao_verificado_e_nunca_ok(tmp_path):
    (tmp_path / "bom.md").write_text("texto limpo\n", encoding="utf-8")
    r = rodar(["."], tmp_path)
    assert "NAO_VERIFICADO" in r.stdout
    assert "OK" not in r.stdout.replace("NAO_VERIFICADO", "")


def test_exigir_lista_sem_lista_sai_3(tmp_path):
    (tmp_path / "bom.md").write_text("texto limpo\n", encoding="utf-8")
    assert rodar([".", "--exigir-lista"], tmp_path).returncode == 3


def test_com_lista_privada_acha_termo(tmp_path):
    negra = tmp_path / "fora" / "negra.txt"
    negra.parent.mkdir()
    negra.write_text("zeta-quux\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("fala do Zeta-Quux aqui\n", encoding="utf-8")
    r = rodar(["x.md"], tmp_path, negra=negra)
    assert r.returncode == 1 and "lista-negra" in r.stdout
    assert "NAO_VERIFICADO" not in r.stdout


def test_arquivo_chamado_negra_txt_e_ignorado(tmp_path):
    (tmp_path / "negra.txt").write_text(f"{EMAIL}\n{CAMINHO}\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "negra.txt").write_text(EMAIL + "\n", encoding="utf-8")
    assert rodar(["."], tmp_path).returncode == 0


def test_arquivo_chamado_negra_txt_passado_direto_tambem_e_ignorado(tmp_path):
    (tmp_path / "negra.txt").write_text(EMAIL + "\n", encoding="utf-8")
    assert rodar(["negra.txt"], tmp_path).returncode == 0


def test_ignorar_arquivo_e_sem_ignorar(tmp_path):
    (tmp_path / "plantado.md").write_text(f"vaza {CAMINHO}\n", encoding="utf-8")
    (tmp_path / ".vazamentoignore").write_text("# fixture\nplantado.md\n", encoding="utf-8")
    assert rodar(["."], tmp_path).returncode == 0
    assert rodar([".", "--sem-ignorar"], tmp_path).returncode == 1


def test_binario_e_git_sao_pulados(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(EMAIL, encoding="utf-8")
    (tmp_path / "img.bin").write_bytes(b"\xff\xfe\x00" + EMAIL.encode())
    assert rodar(["."], tmp_path).returncode == 0


def test_saida_nao_ecoa_o_dado(tmp_path):
    (tmp_path / "x.md").write_text(f"{EMAIL} {CAMINHO}\n", encoding="utf-8")
    r = rodar(["."], tmp_path)
    assert "fulano" not in r.stdout


def test_dot_git_arquivo_de_worktree_e_pulado(tmp_path):
    (tmp_path / ".git").write_text(f"gitdir: {CAMINHO}/repo/.git/worktrees/x\n", encoding="utf-8")
    assert rodar(["."], tmp_path).returncode == 0
    assert rodar([".git"], tmp_path).returncode == 0


# ---- fail-open e normalização (revisão de segurança do commit) ---------------

def test_utf8_invalido_nao_esconde_vazamento(tmp_path):
    (tmp_path / "x.md").write_bytes(b"\xe9\xff lixo\nmail " + EMAIL.encode() + b"\n")
    r = rodar(["."], tmp_path)
    assert r.returncode == 1 and "x.md:2: email" in r.stdout


def test_utf16_com_bom_e_lido(tmp_path):
    (tmp_path / "x.md").write_bytes(("mail " + EMAIL + "\n").encode("utf-16"))
    assert rodar(["."], tmp_path).returncode == 1


def test_arquivo_ilegivel_e_nao_verificado_e_nunca_limpo(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("limpo\n", encoding="utf-8")
    f.chmod(0)
    try:
        r = rodar(["."], tmp_path)
    finally:
        f.chmod(0o644)
    assert r.returncode == 2 and "NAO_VERIFICADO" in r.stdout and "x.md" in r.stdout


@pytest.mark.parametrize("linha", [
    "zeta\u200b-quux", "ZETA\u00ad-QUUX", "ｚｅｔａ-ｑｕｕｘ", "zeta\ufeff-quux",
])
def test_lista_resiste_a_zero_width_e_largura_total(linha):
    assert v.chk_lista(v.normalizar(linha), ["zeta-quux"])


def test_email_e_caminho_resistem_a_largura_total():
    cheia = lambda t: "".join(chr(ord(c) + 0xFEE0) if c != " " else c for c in t)  # ASCII -> largura total
    assert v.chk_email(v.normalizar("fulano" + cheia("@") + "empresa.com.br"))
    assert v.chk_caminho(v.normalizar(cheia("/Users/") + "fulano"))


@pytest.mark.parametrize("linha", ["/users/" + "fulano", "C:\\Users\\" + "fulano\\x", "/USERS/" + "fulano"])
def test_caminho_caixa_e_windows(linha):
    assert v.chk_caminho(linha)


def test_zero_width_na_varredura_de_ponta_a_ponta(tmp_path):
    negra = tmp_path / "fora" / "negra.txt"
    negra.parent.mkdir()
    negra.write_text("zeta-quux\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("fala do zeta\u200b-quux aqui\n", encoding="utf-8")
    assert rodar(["x.md"], tmp_path, negra=negra).returncode == 1


def test_negra_txt_no_stage_bloqueia_o_commit(tmp_path):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True)
    git("init", "-q")
    (tmp_path / "negra.txt").write_text("termo\n", encoding="utf-8")
    assert git("add", "-f", "negra.txt").returncode == 0
    r = rodar(["--staged"], tmp_path)
    assert r.returncode == 1 and "negra-no-stage" in r.stdout


# ---- allowlists e fail-open (2ª revisão de segurança) ------------------------

def test_isencao_example_nao_cobre_dominio_real_que_comeca_com_example():
    assert v.chk_email("fulano" + "@" + "example.com.br")
    assert v.chk_email("fulano" + "@" + "example.com-corp.io")
    assert v.chk_email("escreva para fulano@example.com.") == []
    assert v.chk_email("lista: a@example.com, b@example.org;") == []


def test_email_seguido_de_dois_pontos_ainda_vaza_mas_scp_do_git_nao():
    assert v.chk_email("contato " + EMAIL + ": telefone abaixo")
    assert v.chk_email("git clone git@github.com:org/repo.git") == []
    assert v.chk_email("ssh@servidor.dev:/srv") == []


def test_lista_negra_vazia_ou_so_comentario_e_nao_verificado(tmp_path):
    (tmp_path / "bom.md").write_text("limpo\n", encoding="utf-8")
    for conteudo in ("", "\n\n", "# só comentário\n"):
        negra = tmp_path / "vazia.txt"
        negra.write_text(conteudo, encoding="utf-8")
        r = rodar([".", "--exigir-lista"], tmp_path, negra=negra)
        assert "NAO_VERIFICADO" in r.stdout and r.returncode == 3, conteudo


def test_lista_negra_com_byte_invalido_nao_derruba_nem_some(tmp_path):
    negra = tmp_path / "fora.txt"
    negra.write_bytes(b"zeta-quux\n\xff\xfe quebrado\n")
    (tmp_path / "x.md").write_text("zeta-quux\n", encoding="utf-8")
    assert rodar(["x.md"], tmp_path, negra=negra).returncode == 1


def test_caminho_inexistente_nao_e_limpo(tmp_path):
    r = rodar(["nao-existe"], tmp_path)
    assert r.returncode == 2 and "nao-existe" in (r.stdout + r.stderr)


def test_pasta_venv_e_node_modules_nao_sao_isentas(tmp_path):
    for d in ("venv", "node_modules", "sub/venv"):
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "x.md").write_text(EMAIL + "\n", encoding="utf-8")
    r = rodar(["."], tmp_path)
    assert r.returncode == 1 and len([l for l in r.stdout.splitlines() if ": email" in l]) == 3


def test_negra_txt_versionado_e_achado_no_scan_de_repo(tmp_path):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True)
    git("init", "-q")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "negra.txt").write_text("termo\n", encoding="utf-8")
    (tmp_path / "negra.txt").write_text("termo\n", encoding="utf-8")
    git("add", "-f", "docs/negra.txt")
    r = rodar(["."], tmp_path)
    assert r.returncode == 1 and "docs/negra.txt:0: negra-no-repo" in r.stdout
    assert "\nnegra.txt:" not in "\n" + r.stdout  # o não versionado segue ignorado


def test_isencao_do_vazamentoignore_aparece_na_saida(tmp_path):
    (tmp_path / "plantado.md").write_text(f"vaza {CAMINHO}\n", encoding="utf-8")
    (tmp_path / ".vazamentoignore").write_text("plantado.md\n", encoding="utf-8")
    r = rodar(["."], tmp_path)
    assert r.returncode == 0 and "isento" in r.stdout and "plantado.md" in r.stdout


def test_lista_negra_padrao_mora_fora_do_repo_em_config_cogiforge():
    assert v.NEGRA_PADRAO == Path.home() / ".config" / "cogiforge" / "negra.txt"
