#!/usr/bin/env python3
"""hub.py: a raiz de cada projeto aponta para TODOS os .md do projeto.

Em vault/projects/<nome>/instructions.md existe um bloco GERADO entre dois marcadores. O script
regrava so esse bloco, com um wikilink de caminho completo a partir de vault/
(`[[projects/<nome>/arquivo|arquivo]]`) para cada .md do projeto. Caminho completo e a unica forma
que o Obsidian resolve sem ambiguidade. Lista escrita a mao nao acompanha o projeto; a gerada sim.

Uso:
    python3 ferramentas/hub.py              # regrava o bloco em cada raiz de projeto
    python3 ferramentas/hub.py --check      # rc=1 se o disco difere do gerado (nao grava)
    python3 ferramentas/hub.py --dry-run    # imprime o bloco de cada projeto, nao grava
    python3 ferramentas/hub.py --selftest
    python3 ferramentas/hub.py --vault DIR  # outro vault (testes)

Regra de admissao: se vault/projects/_index.md existe, todo projeto precisa aparecer nele.
Pasta de projeto sem instructions.md e reportada, nunca inventada.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ABRE, FECHA = "<!-- hub:inicio -->", "<!-- hub:fim -->"
VAULT = Path(__file__).resolve().parent.parent / "vault"


def listar(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.rglob("*.md") if p != pasta / "instructions.md")


def gerar(pasta: Path, vault: Path) -> str:
    arquivos = listar(pasta)
    linhas = [ABRE]
    linhas += [_link(p, vault) for p in arquivos]
    if not arquivos:
        linhas.append("_(nenhum outro arquivo ainda)_")
    return "\n".join(linhas + [FECHA])


def _link(p: Path, vault: Path) -> str:
    rel = p.relative_to(vault).with_suffix("").as_posix()
    if any(c in p.stem for c in "|#") or "]]" in p.stem:
        return f"- `{rel}` (titulo com caractere que quebra wikilink)"
    return f"- [[{rel}|{p.stem}]]"


def bloco_atual(texto: str) -> str | None:
    i, j = texto.find(ABRE), texto.find(FECHA)
    return texto[i:j + len(FECHA)] if 0 <= i < j else None


def processar(pasta: Path, vault: Path, check: bool, dry: bool) -> str:
    raiz = pasta / "instructions.md"
    if not raiz.is_file():
        return "SEM RAIZ"
    novo, texto = gerar(pasta, vault), raiz.read_text(encoding="utf-8")
    atual = bloco_atual(texto)
    if atual is None and not listar(pasta):
        return "OK"  # sem bloco e sem arquivos extras: nada a registrar, nada a mexer
    if dry:
        print(f"# {pasta.name}\n{novo}\n")
        return "dry"
    if atual == novo:
        return "OK"
    if check:
        return "SEM BLOCO" if atual is None else "STALE"
    final = texto.replace(atual, novo) if atual else texto.rstrip() + "\n\n" + novo + "\n"
    raiz.write_text(final, encoding="utf-8")
    return "gravado"


def faltando_no_indice(vault: Path, projetos: list[Path]) -> list[str]:
    indice = vault / "projects" / "_index.md"
    if not indice.is_file():
        return []
    texto = indice.read_text(encoding="utf-8")
    return [p.name for p in projetos if p.name not in texto]


def rodar(vault: Path, check: bool, dry: bool) -> int:
    base = vault / "projects"
    projetos = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    ruim = 0
    for p in projetos:
        st = processar(p, vault, check, dry)
        print(f"{st:10} {p.name}")
        ruim += st in ("STALE", "SEM BLOCO", "SEM RAIZ")
    for nome in faltando_no_indice(vault, projetos):
        print(f"FORA DO INDICE {nome}  (todo projeto entra em projects/_index.md)")
        ruim += 1
    return 1 if check and ruim else 0


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        v = Path(td)
        p = v / "projects" / "x"
        p.mkdir(parents=True)
        (p / "instructions.md").write_text("# x\n")
        vazio = rodar(v, check=True, dry=False)
        (p / "a.md").write_text("a")
        stale = rodar(v, check=True, dry=False)
        rodar(v, check=False, dry=False)
        depois = rodar(v, check=True, dry=False)
    ok = (vazio, stale, depois) == (0, 1, 0)
    print("selftest:", "OK" if ok else f"FALHOU {(vazio, stale, depois)}")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    conhecidas = {"--check", "--dry-run", "--selftest", "--vault"}
    pos = [a for i, a in enumerate(argv) if a not in conhecidas and not (i and argv[i - 1] == "--vault")]
    if pos:
        print(f"flag desconhecida: {pos[0]} (nada foi gravado)", file=sys.stderr)
        return 2
    if "--selftest" in argv:
        return selftest()
    vault = Path(argv[argv.index("--vault") + 1]) if "--vault" in argv else VAULT
    return rodar(vault, "--check" in argv, "--dry-run" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
