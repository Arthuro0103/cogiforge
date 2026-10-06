#!/usr/bin/env python3
"""portao.py — transforma regra escrita em regra rodada. Só stdlib.

    portao.py [--vault vault] [--json] [--check NOME ...] [ARQUIVO.md ...]

Os 5 checks:
  frontmatter   o bloco entre `---` parseia (parser próprio, subconjunto abaixo)
  area          `area:` está na lista configurada e casa com a pasta `notes/<pasta>/`
  link-morto    todo [[wikilink]] resolve (raiz > relativo à nota > nome em qualquer pasta)
  link-partido  `[[` abre e fecha na MESMA linha (o Obsidian não resolve link quebrado em duas)
  alvo-morto    `alvo:` do frontmatter aponta para algo que existe

Código (bloco cercado e `inline`) não conta como link. rc: 0 limpo · 1 reprova · 2 uso · 3 não deu pra ler.

Áreas: `<vault>/areas.txt`, uma por linha, `area` (a pasta tem o mesmo nome) ou `pasta: area`.
Sem o arquivo valem as 3 de exemplo (learning, technology, life). Só vale dentro de `notes/`.

SUBCONJUNTO DE YAML aceito no frontmatter (fora dele reprova, em vez de adivinhar):
  chave: valor            valor simples, 'aspas simples' ou "aspas duplas" (valor simples não
                          pode ter `: ` nem terminar em `:`; ponha aspas)
  chave:                  vazio, ou seguido de linhas `  - item` (lista)
  chave: [a, "b c"]       lista numa linha só
  # comentário            linha inteira ou ` #` no fim de valor simples
Não aceita: mapa aninhado, `|` e `>` (texto em bloco), âncoras `&`/`*`, tags `!`, tabulação
na indentação, frontmatter que abre com `---` e nunca fecha.
"""
import argparse
import json
import os
import re
import sys
from collections import namedtuple
from pathlib import Path

Falha = namedtuple("Falha", "arquivo check msg")

CHECAGENS = [
    ("frontmatter", "frontmatter parseia"),
    ("area", "area: configurada e casando com a pasta"),
    ("link-morto", "todo wikilink resolve"),
    ("link-partido", "`[[` abre e fecha na mesma linha"),
    ("alvo-morto", "alvo: aponta pra algo que existe"),
]
AREAS_PADRAO = {"learning": "learning", "technology": "technology", "life": "life"}
IGNORAR_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
EXTS = (".md", ".canvas", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".txt", ".json",
        ".excalidraw", ".mp4", ".mp3")

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE = re.compile(r"`[^`\n]*`")
WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")


class ErroFM(Exception):
    pass


def mascarar(texto):
    """Esvazia blocos cercados e `código inline`, preservando o número de linhas."""
    out, cerca = [], None
    for linha in texto.split("\n"):
        m = FENCE.match(linha)
        if cerca is None:
            if m:
                cerca = (m.group(1)[0], len(m.group(1)))
                out.append("")
            else:
                out.append(INLINE.sub(lambda x: " " * len(x.group(0)), linha))
        else:
            if m and m.group(1)[0] == cerca[0] and len(m.group(1)) >= cerca[1] and linha.strip() == m.group(1):
                cerca = None
            out.append("")
    return "\n".join(out)


def alvo_do_link(bruto):
    alvo = bruto.replace("\\|", "|").split("|", 1)[0]
    return re.split(r"[#^]", alvo, maxsplit=1)[0].strip()


def wikilinks(texto_mascarado):
    """[(alvo, linha)] — âncora do próprio arquivo ([[#x]]) não entra."""
    return [(alvo_do_link(m.group(2)), texto_mascarado.count("\n", 0, m.start()) + 1)
            for m in WIKILINK.finditer(texto_mascarado) if alvo_do_link(m.group(2))]


# ---- frontmatter: parser mínimo -----------------------------------------------

def escalar(v):
    v = v.strip()
    if v[:1] in "\"'":
        if len(v) < 2 or v[-1] != v[0]:
            raise ErroFM("aspas sem fechar")
        return v[1:-1]
    if v[:1] == "[":
        if not v.endswith("]"):
            raise ErroFM("lista inline sem fechar")
        itens = re.findall(r"\"[^\"]*\"|'[^']*'|[^,]+", v[1:-1])
        return [escalar(i) for i in itens if i.strip()]
    if v[:1] in "{|>&*!%@`":
        raise ErroFM(f"`{v[0]}` fora do subconjunto aceito")
    v = re.sub(r"\s+#.*$", "", v)
    if ": " in v or v.endswith(":"):
        raise ErroFM("dois-pontos sem aspas no valor")
    return v


def parse_fm(linhas):
    """(dict, None) ou (parcial, (linha, motivo)). A linha conta a partir do `---` de abertura."""
    d, ultima = {}, None
    for n, bruta in enumerate(linhas, start=2):
        s = bruta.rstrip()
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        try:
            if "\t" in s[:len(s) - len(s.lstrip())]:
                raise ErroFM("tabulação na indentação")
            item = re.match(r"^\s*-\s+(.+)$", s)
            if s[0] in " -":
                if not item or ultima is None:
                    raise ErroFM("indentação fora do subconjunto (mapa aninhado?)")
                if d[ultima] is None:
                    d[ultima] = []
                if not isinstance(d[ultima], list):
                    raise ErroFM("item de lista depois de um valor que não é lista")
                d[ultima].append(escalar(item.group(1)))
                continue
            m = re.match(r"^([\w-]+)\s*:(?:\s+(.*))?$", s)
            if not m:
                raise ErroFM(f"linha sem 'chave: valor': {s.strip()[:40]!r}")
            ultima = m.group(1)
            d[ultima] = escalar(m.group(2)) if m.group(2) is not None and m.group(2).strip() else None
        except ErroFM as e:
            return d, (n, str(e))
    return d, None


def separar_frontmatter(linhas):
    """(linhas do bloco | None, erro | None)."""
    if not linhas or linhas[0].strip() != "---":
        return None, None
    for i in range(1, len(linhas)):
        if linhas[i].strip() in ("---", "..."):
            return linhas[1:i], None
    return None, (1, "abre com --- e nunca fecha")


# ---- índice e nota ------------------------------------------------------------

class Indice:
    def __init__(self, raiz, areas=None):
        self.raiz = Path(raiz)
        self.caminhos, self.nomes = {}, {}   # relpath lower -> relpath ; filename lower -> [relpath]
        for dirpath, dirs, nomes in os.walk(self.raiz):
            dirs[:] = sorted(d for d in dirs if d not in IGNORAR_DIRS)
            for fn in sorted(nomes):
                if fn.startswith("."):
                    continue
                rel = (Path(dirpath) / fn).relative_to(self.raiz).as_posix()
                self.caminhos[rel.lower()] = rel
                self.nomes.setdefault(fn.lower(), []).append(rel)
        self.areas = areas if areas is not None else ler_areas(self.raiz)

    def achar(self, alvo, origem):
        """relpath do arquivo que o link resolve, ou None.
        Camadas: raiz > relativo à nota > (com barra) sufixo de caminho | (sem barra) nome em qualquer pasta."""
        alvo = alvo.strip().replace("\\", "/")
        if not alvo:
            return None
        tem_ext = alvo.lower().endswith(EXTS)
        cands = [alvo] if tem_ext else [alvo, alvo + ".md"]
        for c in cands:
            if c.lstrip("/").lower() in self.caminhos:
                return self.caminhos[c.lstrip("/").lower()]
        base = os.path.dirname(origem)
        for c in cands:
            r = os.path.normpath(os.path.join(base, c)).replace("\\", "/")
            if r.lower() in self.caminhos:
                return self.caminhos[r.lower()]
        if "/" in alvo:  # com caminho: casa por sufixo de caminho, como o Obsidian; nunca só pelo nome
            for c in cands:
                for baixo, rel in self.caminhos.items():
                    if baixo.endswith("/" + c.lower()):
                        return rel
            return None
        n = alvo.lower() if tem_ext else alvo.lower() + ".md"
        if n in self.nomes:
            return self.nomes[n][0]  # a nota da mesma pasta já foi achada na camada relativa
        return None


def ler_areas(raiz):
    """{pasta: area}. `areas.txt` na raiz do vault, ou as 3 de exemplo."""
    f = Path(raiz) / "areas.txt"
    if not f.is_file():
        return dict(AREAS_PADRAO)
    areas = {}
    for linha in f.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            pasta, _, area = linha.partition(":")
            areas[pasta.strip()] = (area or pasta).strip()
    return areas


class Nota:
    def __init__(self, vault, path):
        self.rel = Path(path).relative_to(vault).as_posix()
        self.path = Path(path)
        self.texto = Path(path).read_bytes().decode("utf-8")  # UnicodeDecodeError -> ilegível (ver auditar)
        linhas = self.texto.split("\n")
        bloco, self.fm_erro = separar_frontmatter(linhas)
        self.fm = {}
        if bloco is not None:
            self.fm, self.fm_erro = parse_fm(bloco)
        self.sem_codigo = mascarar(self.texto)


# ---- os 5 checks --------------------------------------------------------------

PASTAS_DO_PLUGIN = ("tasks",)  # o YAML daqui é do TaskNotes (ex.: timeEntries, lista de mapas), não do subconjunto


def chk_frontmatter(n, idx):
    if not n.fm_erro or Path(n.rel).parts[0] in PASTAS_DO_PLUGIN:
        return []
    return [Falha(n.rel, "frontmatter", f"yaml fora do subconjunto: {n.fm_erro[1]} (linha {n.fm_erro[0]})")]


def chk_area(n, idx):
    partes = Path(n.rel).parts
    if partes[0] != "notes":
        return []
    areas = idx.areas
    if len(partes) < 3:
        return [Falha(n.rel, "area", f"nota solta na raiz de notes/: mova para notes/<pasta>/ "
                                     f"(pastas: {', '.join(sorted(areas))})")]
    if n.fm_erro:
        return []  # já reprovou em frontmatter; não contar duas vezes
    pasta, area = partes[1], n.fm.get("area")
    esperada = areas.get(pasta)
    if esperada is None:
        return [Falha(n.rel, "area", f"a pasta '{pasta}' não é de nenhuma área configurada")]
    if area is None or not str(area).strip():
        return [Falha(n.rel, "area", f"sem campo area: (a pasta '{pasta}' pede '{esperada}')")]
    area = str(area).strip()
    if area not in areas.values():
        return [Falha(n.rel, "area", f"area: '{area}' não está na lista configurada ({', '.join(sorted(set(areas.values())))})")]
    if area != esperada:
        pasta_da_area = next(p for p, a in areas.items() if a == area)
        return [Falha(n.rel, "area", f"area: '{area}' mora em notes/{pasta_da_area}/, mas o arquivo está em notes/{pasta}/")]
    return []


def chk_link_morto(n, idx):
    return [Falha(n.rel, "link-morto", f"[[{alvo}]] não resolve (linha {ln})")
            for alvo, ln in wikilinks(n.sem_codigo) if idx.achar(alvo, n.rel) is None]


def chk_link_partido(n, idx):
    out = []
    for i, linha in enumerate(n.sem_codigo.split("\n"), 1):
        resto = re.sub(r"\[\[[^\]\n]*\]\]", "", linha)
        if "[[" in resto:
            out.append(Falha(n.rel, "link-partido", f"`{resto[resto.index('[['):][:40].strip()}` não fecha na linha {i}"))
    return out


def chk_alvo(n, idx):
    alvo = n.fm.get("target")
    if alvo is None:
        return []
    out = []
    for a in alvo if isinstance(alvo, list) else [alvo]:
        a = str(a).strip().strip("[]").strip()
        if not a or a.lower() == "none":
            continue
        # disco primeiro (cobre diretório e caminho absoluto); nome puro sem barra vale como nome de nota
        cands = [idx.raiz / a, idx.raiz / (a + ".md")]  # pathlib: `raiz / "/abs"` já é "/abs"
        if any(c.exists() for c in cands) or ("/" not in a and idx.achar(a, n.rel) is not None):
            continue
        out.append(Falha(n.rel, "alvo-morto", f"alvo: '{a}' não existe no disco"))
    return out


ORDEM = [chk_frontmatter, chk_area, chk_link_morto, chk_link_partido, chk_alvo]


# ---- varredura ----------------------------------------------------------------

def coletar(vault, alvos=None):
    achados = []
    for base in alvos or [vault]:
        base = Path(base)
        if base.is_file():
            achados.append(base)
            continue
        for dirpath, dirs, nomes in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in IGNORAR_DIRS)
            achados += [Path(dirpath) / f for f in sorted(nomes) if f.endswith(".md") and not f.startswith(".")]
    return achados


def auditar(vault, arquivos=None, areas=None, checks=None):
    """(arquivos .md varridos, [Falha | Ilegivel])."""
    vault = Path(vault)
    idx = Indice(vault, areas)
    todos = coletar(vault, arquivos)
    falhas = []
    for p in todos:
        try:
            n = Nota(vault, p)
        except (OSError, UnicodeDecodeError) as e:
            falhas.append(Falha(Path(p).relative_to(vault).as_posix(), "ILEGIVEL", f"{type(e).__name__}"))
            continue
        for fn in ORDEM:
            falhas += [f for f in fn(n, idx) if not checks or f.check in checks]
    return todos, falhas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="*")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="append", help="roda só este check (repetível)")
    args = ap.parse_args(argv)
    vault = Path(args.vault)
    nomes = {c for c, _ in CHECAGENS}
    if not vault.is_dir() or (args.check and set(args.check) - nomes):
        print(f"ERRO: vault inexistente ({vault}) ou check desconhecido (válidos: {', '.join(sorted(nomes))})", file=sys.stderr)
        return 2
    alvos = []
    for a in args.arquivos:
        arq = Path(a) if Path(a).exists() else vault / a
        try:
            arq.resolve().relative_to(vault.resolve())
        except ValueError:
            print(f"ERRO: {a} está fora de {vault}. O portão resolve link e área a partir do vault: dar OK a "
                  f"um arquivo que ele não conferiu é pior que não rodar. Copie o arquivo pra dentro do vault.",
                  file=sys.stderr)
            return 2
        alvos.append(arq)
    alvos = alvos or None
    todos, achados = auditar(vault, alvos, checks=set(args.check or []))
    ileg = [f for f in achados if f.check == "ILEGIVEL"]
    falhas = [f for f in achados if f.check != "ILEGIVEL"]
    reprovadas = {f.arquivo for f in falhas}
    por = {c: [f for f in falhas if f.check == c] for c, _ in CHECAGENS}
    if args.json:
        print(json.dumps({
            "arquivos": len(todos), "reprovadas": len(reprovadas), "ilegiveis": [f.arquivo for f in ileg],
            "checagens": {c: {"notas": len({f.arquivo for f in fs}), "ocorrencias": len(fs)} for c, fs in por.items()},
            "falhas": [f._asdict() for f in falhas]}, ensure_ascii=False, indent=2))
    else:
        for f in ileg:
            print(f"ILEGIVEL {f.arquivo} :: {f.msg}")
        for f in falhas:
            print(f"REPROVA {f.arquivo} :: {f.check} :: {f.msg}")
        print(f"\n{len(todos)} nota(s), {len(reprovadas)} reprovam, {len(ileg)} NAO DEU PRA LER")
        for c, d in CHECAGENS:
            print(f"  {c:<13}{len(por[c]):>4}  {d}")
    return 3 if ileg else (1 if falhas else 0)


if __name__ == "__main__":
    sys.exit(main())
