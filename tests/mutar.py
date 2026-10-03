#!/usr/bin/env python3
"""mutar.py — mata cada check de cada peça, um de cada vez, e exige a suíte vermelha.

Dois operadores:
  chk     injeta `return []` como 1ª linha de todo `def chk_*` (o check passa a nunca reprovar);
  texto   troca um trecho exato por outro (um comportamento que não é `chk_`: ignorar
          `negra.txt`, a isenção do inbox, o `exit 1` do hook...). O trecho tem que existir
          UMA vez; se não existir, o mutante é "inaplicável" e conta como falha da ferramenta.

Placar igual não prova nada: o script imprime o NOME dos testes que falham, limpa o bytecode
a cada rodada e roda com PYTHONDONTWRITEBYTECODE=1.

    python3 tests/mutar.py                 todas as peças
    python3 tests/mutar.py vazamento anel  só essas
rc: 0 todo mutante morto · 1 sobrou mutante vivo · 2 suíte já vermelha / mutante inaplicável
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PECAS = {
    "vazamento": dict(arquivo="nucleo/vazamento.py", suite=["tests/test_vazamento.py"], textos=[
        ("ignora negra.txt", 'if texto is None or Path(nome).name == NOME_NEGRA:', 'if texto is None:'),
        ("ignora .vazamentoignore", 'if os.path.normpath(nome) in ignorados:', 'if False:'),
        ("exigir-lista não falha", 'return 3', 'return 0'),
        ("achado não reprova", 'return 1 if total else (2 if ilegiveis else 0)', 'return 0'),
        ("ausência vira OK", 'print("NAO_VERIFICADO:', 'print("OK:'),
        ("lista sensível à caixa", 'baixa = linha.casefold()', 'baixa = linha'),
        ("negra não pula comentário", ' and not t.lstrip().startswith("#")', ''),
        ("varre .git", 'PULAR_DIRS = {".git", ', 'PULAR_DIRS = {'),
        ("ecoa o dado", 'print(f"{nome}:{n}: {tipo}")', 'print(f"{nome}:{n}: {tipo} {texto.splitlines()[n-1]}")'),
        ("sem NFKC", 'unicodedata.normalize("NFKC", texto)', 'texto'),
        ("zero-width não sai", 'if unicodedata.category(c) != "Cf")', 'if True)'),
        ("caminho sensível à caixa", '[A-Za-z0-9._-]+", re.IGNORECASE)', '[A-Za-z0-9._-]+")'),
        ("negra.txt no stage passa", '(args.staged or os.path.normpath(nome) in versionados)', 'os.path.normpath(nome) in versionados'),
        ("ilegível vira limpo", 'return 1 if total else (2 if ilegiveis else 0)', 'return 1 if total else 0'),
        ("utf-16 pulado", 'return dados.decode("utf-16", errors="replace")', 'return None'),
        ("utf-8 inválido pulado", 'return dados.decode("utf-8", errors="replace")', 'return None'),
        ("example.com.br isento", '(?:com|org|net)(?![\\w-]|\\.\\w))', '(?:com|org|net)\\b)'),
        ("e-mail com ':' isento", 'm.group(1) in SCP_USUARIOS and linha', 'True and linha'),
        ("lista vazia vira verificada", 'return termos or None', 'return termos'),
        ("caminho inexistente passa", 'if inexistentes:', 'if False:'),
        ("venv isento", '".pytest_cache"}', '".pytest_cache", "venv"}'),
        ("negra.txt versionado passa", '(args.staged or os.path.normpath(nome) in versionados)', 'args.staged'),
        ("isenção silenciosa", 'isentos.append(nome)', 'pass'),
        ("e-mail example.com vaza", r'(?!example\.(?:com|org|net)(?![\w-]|\.\w))', ''),
    ]),
    "portao": dict(arquivo="nucleo/portao.py", suite=["tests/test_portao.py", "tests/test_demo.py"], textos=[]),
    "anel": dict(arquivo="nucleo/anel.py", suite=["tests/test_anel.py", "tests/test_demo.py"], textos=[]),
    "hook": dict(arquivo=".githooks/pre-commit", suite=["tests/test_hook_e2e.py"], textos=[]),
}


def checks(fonte):
    return re.findall(r"^def (chk_\w+)\(", fonte, re.M)


def mutar_chk(fonte, alvo):
    padrao = re.compile(rf"(^def {re.escape(alvo)}\([^)]*\)[^:\n]*:\n)((?:\s*(?:\"\"\".*?\"\"\"|'''.*?''')\n)?)",
                        re.M | re.S)
    m = padrao.search(fonte)
    if not m:
        raise LookupError(alvo)
    return fonte[:m.end()] + "    return []  # MUTANTE\n" + fonte[m.end():]


def mutar_texto(fonte, antigo, novo):
    if fonte.count(antigo) != 1:
        raise LookupError(f"{antigo!r} aparece {fonte.count(antigo)}x")
    return fonte.replace(antigo, novo)


def rodar(suite):
    for d in RAIZ.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", *suite, "-q", "--no-header", "-x",
                        "-p", "no:cacheprovider", "-W", "ignore"],
                       capture_output=True, text=True, cwd=RAIZ, env=env)
    falhos = sorted(set(re.findall(r"^FAILED\s+\S*::(\S+)", r.stdout, re.M)))
    return r.returncode, falhos


def mutantes(peca, fonte):
    for c in checks(fonte):
        yield f"chk:{c}", lambda f, c=c: mutar_chk(f, c)
    for nome, antigo, novo in PECAS[peca]["textos"]:
        yield f"texto:{nome}", lambda f, a=antigo, n=novo: mutar_texto(f, a, n)


def main():
    alvos = sys.argv[1:] or list(PECAS)
    vivos, inaplicaveis, total = [], [], 0
    for peca in alvos:
        spec = PECAS[peca]
        arq = RAIZ / spec["arquivo"]
        if not arq.exists():
            print(f"[{peca}] {spec['arquivo']} não existe ainda — pulado")
            continue
        original = arq.read_text(encoding="utf-8")
        rc, _ = rodar(spec["suite"])
        if rc != 0:
            print(f"[{peca}] a suíte já está VERMELHA sem mutação — conserte antes de mutar.")
            return 2
        print(f"[{peca}] baseline verde")
        try:
            for nome, fn in mutantes(peca, original):
                try:
                    novo = fn(original)
                except LookupError as e:
                    inaplicaveis.append(f"{peca}/{nome}")
                    print(f"  INAPLICÁVEL {nome}: {e}")
                    continue
                total += 1
                arq.write_text(novo, encoding="utf-8")
                rc, falhos = rodar(spec["suite"])
                if rc == 0:
                    vivos.append(f"{peca}/{nome}")
                    print(f"  SOBREVIVEU  {nome}")
                else:
                    print(f"  morto       {nome:45} {', '.join(falhos[:2]) or '(sem nome capturado)'}")
        finally:
            arq.write_text(original, encoding="utf-8")
    print(f"\n{total - len(vivos)} de {total} mutantes mortos; {len(vivos)} vivos; {len(inaplicaveis)} inaplicáveis")
    for v in vivos:
        print("  vivo:", v)
    return 2 if inaplicaveis else (1 if vivos else 0)


if __name__ == "__main__":
    sys.exit(main())
