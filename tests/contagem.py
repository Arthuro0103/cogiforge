"""Contagem exata por check sobre demo/ — a meta-asserção da fixture.

Se a fixture parar de exercitar um check (alguém apaga a nota plantada, ou o check morre e
a nota passa), o número muda e o CI cai. Rodável sozinho: `python3 tests/contagem.py`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEMO = RAIZ / "demo"

# check -> o ÚNICO arquivo que o reprova (o nome do arquivo diz qual falha ele carrega)
ESPERADO = {
    "orfa": "notas/aprendizado/orfa.md",
    "link-morto": "notas/aprendizado/link-morto.md",
    "link-partido": "notas/aprendizado/link-partido.md",
    "alvo-morto": "notas/aprendizado/alvo-morto.md",
    "area": "notas/tecnologia/area-errada.md",
    "frontmatter": "notas/tecnologia/frontmatter-quebrado.md",
    "vazamento": "notas/vida/vazou.md",
}
TOTAL_NOTAS = 15
ISENTAS_ANEL = ["inbox/captura-solta.md"]


def _rodar(script, *args):
    env = {**os.environ, "VAZAMENTO_NEGRA": str(RAIZ / "ausente-de-proposito.txt"), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(RAIZ / "nucleo" / script), *args],
                          capture_output=True, text=True, cwd=RAIZ, env=env)


def contar():
    """{check: [arquivos que reprova]} mais as chaves '_total' e '_isentas'."""
    achados = {c: [] for c in ESPERADO}
    p = _rodar("portao.py", "--vault", "demo", "--json")
    dados = json.loads(p.stdout)
    for f in dados["falhas"]:
        achados.setdefault(f["check"], []).append(f["arquivo"])
    a = json.loads(_rodar("anel.py", "--vault", "demo", "--json").stdout)
    achados["orfa"] = a["orfas"]
    v = _rodar("vazamento.py", "--sem-ignorar", "demo")
    for linha in v.stdout.splitlines():
        if linha.startswith("demo") and ": " in linha:
            achados["vazamento"].append(linha.split(":")[0].removeprefix("demo/"))
    achados["_total"] = dados["arquivos"]
    achados["_isentas"] = a["isentas"]
    return achados


def main():
    try:
        achados = contar()
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
        print(f"FALHOU: não deu pra medir o demo/ ({type(e).__name__}: {e})")
        return 1
    ruim = 0
    print(f"{'check':<14}{'esperado':>9}{'achado':>8}  arquivo")
    for check, arq in ESPERADO.items():
        got = sorted(achados[check])
        ok = got == [arq]
        ruim += not ok
        print(f"{check:<14}{1:>9}{len(got):>8}  {'ok' if ok else 'DIFERENTE: ' + str(got)}  {arq}")
    extras = sorted(set(achados) - set(ESPERADO) - {"_total", "_isentas"})
    for c in extras:  # um check que reprova e a fixture não planta: o placar mudou
        print(f"{c:<14}{0:>9}{len(achados[c]):>8}  INESPERADO")
        ruim += 1
    print(f"notas varridas: {achados['_total']} (esperado {TOTAL_NOTAS}); isentas do anel: {achados['_isentas']}")
    ruim += achados["_total"] != TOTAL_NOTAS or achados["_isentas"] != ISENTAS_ANEL
    print("FALHOU" if ruim else "OK: contagem exata em todos os checks")
    return 1 if ruim else 0


if __name__ == "__main__":
    sys.exit(main())
