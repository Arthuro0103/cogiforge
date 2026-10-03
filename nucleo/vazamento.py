#!/usr/bin/env python3
"""vazamento.py — reprova texto que carrega dado pessoal antes dele ir pra um repo público.

Pega o PADRÃO, não o contexto: caminho /Users/<nome>, e-mail, telefone BR, CPF formatado e
todo termo da lista negra privada. Só stdlib.

    vazamento.py [CAMINHO ...]     varre arquivos/pastas (default: .)
    vazamento.py --staged          varre o que está no stage do git (usado pelo hook)

A lista negra mora FORA do repo (um termo por linha, sem diferenciar caixa):
    ~/.config/scarbrain/negra.txt        (troque com VAZAMENTO_NEGRA=/outro/caminho)
Sem a lista, só os padrões genéricos rodam e a saída diz `NAO_VERIFICADO` — a parte privada
não foi checada, e isso nunca vira "OK". `--exigir-lista` transforma isso em rc=3.

A saída traz arquivo:linha:tipo e NUNCA o dado achado (o log de CI é público).
Arquivos chamados `negra.txt` são sempre ignorados. `.vazamentoignore` (um caminho por linha,
relativo a onde se roda) isenta fixtures plantadas de propósito; `--sem-ignorar` o desliga.

rc: 0 limpo · 1 achou vazamento · 2 uso/erro ou arquivo ilegível · 3 lista privada exigida e ausente
"""
import argparse
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

NEGRA_PADRAO = Path.home() / ".config" / "scarbrain" / "negra.txt"
NOME_NEGRA = "negra.txt"
ARQUIVO_IGNORE = ".vazamentoignore"
PULAR_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}

CAMINHO_RE = re.compile(r"(?:/|\\)Users(?:/|\\)[A-Za-z0-9._-]+", re.IGNORECASE)  # inclui o estilo Windows
EMAIL_RE = re.compile(
    r"(?<![\w.+-])[\w.+-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b(?!:)")
TELEFONE_RE = re.compile(
    r"(?<![\d(])(?:\+55\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}|\(\d{2}\)\s?9?\d{4}-?\d{4}|\d{2}\s9?\d{4}[-\s]\d{4})(?!\d)")
CPF_RE = re.compile(r"(?<![\d.])\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")


def normalizar(texto):
    """NFKC (largura total vira ASCII) sem os caracteres invisíveis (zero-width, soft hyphen, BOM)."""
    return "".join(c for c in unicodedata.normalize("NFKC", texto) if unicodedata.category(c) != "Cf")


def chk_caminho(linha):
    return ["caminho"] if CAMINHO_RE.search(linha) else []


def chk_email(linha):
    return ["email"] if EMAIL_RE.search(linha) else []


def chk_telefone(linha):
    return ["telefone"] if TELEFONE_RE.search(linha) else []


def chk_cpf(linha):
    return ["cpf"] if CPF_RE.search(linha) else []


def chk_lista(linha, termos):
    baixa = linha.casefold()
    return ["lista-negra"] if any(t in baixa for t in termos) else []


def ler_negra(caminho):
    """Termos em minúsculas, ou None se a lista não existe (≠ lista vazia)."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except OSError:
        return None
    return [normalizar(t).strip().casefold() for t in texto.splitlines()
            if t.strip() and not t.lstrip().startswith("#")]


def achados_do_texto(texto, termos):
    """[(linha, tipo)] — um por tipo por linha."""
    out = []
    for n, linha in enumerate(normalizar(texto).splitlines(), 1):
        tipos = (chk_caminho(linha) + chk_email(linha) + chk_telefone(linha)
                 + chk_cpf(linha) + chk_lista(linha, termos))
        out.extend((n, t) for t in tipos)
    return out


def ler_ignorados(usar):
    if not usar or not Path(ARQUIVO_IGNORE).is_file():
        return set()
    linhas = Path(ARQUIVO_IGNORE).read_text(encoding="utf-8").splitlines()
    return {os.path.normpath(l.strip()) for l in linhas if l.strip() and not l.startswith("#")}


def arquivos_de(caminhos):
    for c in caminhos:
        p = Path(c)
        if p.is_file():
            if p.name not in PULAR_DIRS:  # `.git` de worktree é um ARQUIVO com o caminho da máquina
                yield p
            continue
        for raiz, dirs, nomes in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in PULAR_DIRS)
            for nome in sorted(n for n in nomes if n not in PULAR_DIRS):
                yield Path(raiz) / nome


def decodificar(dados):
    """Texto de um arquivo, ou None se for binário. Nunca descarta por encoding ruim:
    um arquivo com byte inválido ainda pode carregar o e-mail na linha ao lado."""
    if dados[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return dados.decode("utf-16", errors="replace")
    if b"\x00" in dados[:8000]:
        return None
    return dados.decode("utf-8", errors="replace")


def no_stage():
    r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
                       capture_output=True, check=True)
    return [c for c in r.stdout.decode("utf-8").split("\0") if c]


def texto_do_stage(caminho):
    r = subprocess.run(["git", "show", f":{caminho}"], capture_output=True)
    if r.returncode != 0:
        raise OSError(f"git show :{caminho} falhou")
    return decodificar(r.stdout)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--exigir-lista", action="store_true")
    ap.add_argument("--sem-ignorar", action="store_true")
    args = ap.parse_args(argv)

    termos = ler_negra(os.environ.get("VAZAMENTO_NEGRA") or NEGRA_PADRAO)
    ignorados = ler_ignorados(not args.sem_ignorar)

    fontes, ilegiveis = [], []  # fontes: (nome, texto)
    try:
        if args.staged:
            for c in no_stage():
                try:
                    fontes.append((c, texto_do_stage(c)))
                except OSError:
                    ilegiveis.append(c)
        else:
            for p in arquivos_de(args.caminhos or ["."]):
                try:
                    fontes.append((os.path.normpath(p), decodificar(p.read_bytes())))
                except OSError:
                    ilegiveis.append(os.path.normpath(p))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERRO: não deu pra listar o stage do git ({e})", file=sys.stderr)
        return 2

    total, com_achado = 0, 0
    for nome, texto in fontes:
        if args.staged and Path(nome).name == NOME_NEGRA:
            print(f"{nome}:0: negra-no-stage")  # a lista privada nunca pode entrar num commit
            total += 1
            com_achado += 1
            continue
        if texto is None or Path(nome).name == NOME_NEGRA or os.path.normpath(nome) in ignorados:
            continue
        achados = achados_do_texto(texto, termos or [])
        for n, tipo in achados:
            print(f"{nome}:{n}: {tipo}")
        total += len(achados)
        com_achado += bool(achados)

    print(f"{total} achado(s) em {com_achado} arquivo(s), de {len(fontes)} varrido(s)")
    for nome in ilegiveis:
        print(f"{nome}: ilegivel")
    if ilegiveis:
        print(f"NAO_VERIFICADO: {len(ilegiveis)} arquivo(s) não lido(s); o resultado acima não os cobre.")
    if termos is None:
        print("NAO_VERIFICADO: lista negra privada ausente — só os padrões genéricos rodaram. "
              f"Crie {NEGRA_PADRAO} (um termo por linha) para checar a parte privada.")
        if args.exigir_lista:
            return 3
    else:
        print(f"lista privada: {len(termos)} termo(s) checados")
    return 1 if total else (2 if ilegiveis else 0)


if __name__ == "__main__":
    sys.exit(main())
