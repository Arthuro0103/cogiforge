#!/usr/bin/env python3
"""anel.py — nota sem nenhum link (de entrada ou de saída) é órfã. Só stdlib.

    anel.py [--vault vault]                lista as órfãs (rc 0)
    anel.py --gate                         rc 1 se há órfã; é o que o hook roda
    anel.py --gate --stage                 só reprova órfã que está NESTE commit; as de fora viram AVISO
    anel.py --json                         {"total", "orfas", "isentas"}
    anel.py --selftest                     prova que ele falha quando deve (órfã -> rc 1, cura -> rc 0)

Aresta = wikilink `[[x]]` ou link `[t](x.md)` que RESOLVE para outra nota .md. Link morto, link
pra si mesmo, link dentro de código e link pra imagem não contam.
`inbox/` é isento de ser reprovada: a captura rápida não pode ser barrada, porque quem é barrado
na captura desinstala. As notas do inbox ainda valem como ponta de aresta.
rc: 0 ok · 1 reprova · 2 não deu pra verificar (vault inexistente, git indisponível)
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import unquote

from portao import Indice, mascarar, wikilinks

DEPOSITOS = ("inbox",)
MDLINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")


def nfc(s):
    return unicodedata.normalize("NFC", s)


def eh_deposito(rel):
    return any(rel == d or rel.startswith(d + "/") for d in DEPOSITOS)


def analisar(vault):
    """([notas .md], grau de cada uma). Grau = arestas de entrada + saída."""
    idx = Indice(vault, areas={})
    notas = sorted(r for r in idx.caminhos.values() if r.endswith(".md"))
    grau = collections.Counter()
    for rel in notas:
        texto = mascarar(Path(vault, rel).read_bytes().decode("utf-8", errors="replace"))
        alvos = [a for a, _ in wikilinks(texto)] + [unquote(m) for m in MDLINK.findall(texto)]
        for a in alvos:
            r = idx.achar(a, rel)
            if r and r != rel and r.endswith(".md"):
                grau[rel] += 1
                grau[r] += 1
    return notas, grau


def chk_orfas(notas, grau):
    return [r for r in notas if grau[r] == 0 and not eh_deposito(r)]


def chk_no_commit(orfas, no_commit):
    return [r for r in orfas if nfc(r) in no_commit]


def no_stage(vault):
    """.md que este commit cria ou muda, relativos ao vault. `-z`: o git põe aspas em caminho acentuado."""
    r = subprocess.run(["git", "-C", str(vault), "diff", "--cached", "--name-only", "--diff-filter=ACMR",
                        "-z", "--relative"], capture_output=True, check=True)
    return {nfc(c) for c in r.stdout.decode("utf-8").split("\0") if c.endswith(".md")}


ENSINA = """
Como consertar: abra a nota e ligue ela a uma nota que EXISTE com um [[wikilink]] (uma seção
"## De onde veio" ou "## Conexões" resolve), ou aponte pra ela a partir de uma nota existente.
Link pra arquivo que não existe não conta. Só captura rápida? Jogue em inbox/: é isento.
Escape consciente: git commit --no-verify
"""


def gate(vault, so_stage=False):
    if not Path(vault).is_dir():
        print(f"NAO_VERIFICADO: o vault '{vault}' não existe; o gate não julgou nada.")
        return 2
    notas, grau = analisar(vault)
    orfas = chk_orfas(notas, grau)
    fora = []
    if so_stage:
        try:
            bloqueiam = chk_no_commit(orfas, no_stage(vault))
        except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
            print("NAO_VERIFICADO: não consegui ler o stage do git (git ausente, ou o vault não está num repo).")
            return 2
        fora = [o for o in orfas if o not in bloqueiam]
        orfas = bloqueiam
    if fora:
        print(f"AVISO — {len(fora)} órfã(s) FORA deste commit (não bloqueia):")
        print("".join(f"   {o}\n" for o in fora))
    if orfas:
        print(f"REPROVA — {len(orfas)} nota(s) sem nenhum link de entrada ou saída:")
        print("".join(f"   {o}\n" for o in orfas) + ENSINA)
        return 1
    print(f"OK — nenhuma órfã{' neste commit' if so_stage else ''} ({len(notas)} nota(s) vistas).")
    return 0


def selftest():
    falhou = []

    def checa(nome, cond):
        print(f"  {'ok  ' if cond else 'FALHOU'}  {nome}")
        if not cond:
            falhou.append(nome)

    tmp = Path(tempfile.mkdtemp(prefix="anel-selftest-"))
    try:
        def esc(rel, txt):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(txt, encoding="utf-8")

        def rc(**kw):
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                return gate(tmp, **kw)
        esc("a.md", "vai para [[b]]\n")
        esc("b.md", "volta para [[a]]\n")
        checa("vault sem órfã passa (rc 0)", rc() == 0)
        esc("solta.md", "nenhum link aqui\n")
        checa("planta uma órfã: gate reprova (rc 1)", rc() == 1)
        esc("solta.md", "agora ligada a [[a]]\n")
        checa("cura a órfã: gate passa (rc 0)", rc() == 0)
        esc("inbox/captura.md", "ideia solta\n")
        checa("órfã no inbox/ é isenta (rc 0)", rc() == 0)
        esc("morta.md", "só aponta pra [[nao-existe]]\n")
        checa("link morto não é aresta: órfã (rc 1)", rc() == 1)
        os.remove(tmp / "morta.md")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            esc("nova.md", "órfã no commit\n")
            esc("velha.md", "órfã fora do commit\n")
            subprocess.run(["git", "add", "nova.md"], cwd=tmp, check=True)
            checa("--stage reprova a órfã que está no commit (rc 1)", rc(so_stage=True) == 1)
            subprocess.run(["git", "reset", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "add", "a.md"], cwd=tmp, check=True)
            checa("--stage deixa passar órfã de fora do commit (rc 0)", rc(so_stage=True) == 0)
        else:
            print("  NAO_VERIFICADO  git ausente: --stage não foi testado")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST FALHOU: " + "; ".join(falhou) if falhou else "\nSELFTEST OK — o anel falha quando deve")
    return 1 if falhou else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--stage", action="store_true", help="com --gate: só reprova o que está no stage do git")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.gate:
        return gate(args.vault, so_stage=args.stage)
    if not Path(args.vault).is_dir():
        print(f"ERRO: vault inexistente: {args.vault}", file=sys.stderr)
        return 2
    notas, grau = analisar(args.vault)
    orfas = chk_orfas(notas, grau)
    isentas = [r for r in notas if grau[r] == 0 and eh_deposito(r)]
    if args.json:
        print(json.dumps({"total": len(notas), "orfas": orfas, "isentas": isentas}, ensure_ascii=False))
    else:
        for o in orfas:
            print(f"ORFA {o}")
        print(f"{len(orfas)} órfã(s) de {len(notas)} nota(s); {len(isentas)} isenta(s) (inbox/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
