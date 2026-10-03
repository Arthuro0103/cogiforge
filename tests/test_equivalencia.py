"""O portão do template dá o MESMO veredito que o do Brain, nos checks que os dois têm.

O Brain fixa o VAULT pelo caminho do próprio script (`parent.parent`), então o script dele é
copiado para <tmp>/scripts/ e o demo/ para <tmp>/. Sem o Brain (CI público), o teste é PULADO
e o prova.yml imprime NAO_VERIFICADO: pular não é passar.

    COGIFORGE_BRAIN=/caminho/do/Brain pytest tests/test_equivalencia.py -rs

Checks em comum: frontmatter, area, link-morto, link-partido, alvo-morto. Ficam fora, de propósito:
titulo, caminho-morto e sem-link-no-corpo (só existem no Brain). O que a comparação cobre é o que o
demo/ exercita: ela diz "mesmo veredito nestas 15 notas", não "mesmo comportamento em tudo".
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import portao

RAIZ = Path(__file__).resolve().parent.parent
EM_COMUM = ["frontmatter", "area", "link-morto", "link-partido", "alvo-morto"]


def brain():
    b = os.environ.get("COGIFORGE_BRAIN")
    if not b or not (Path(b) / "scripts" / "portao.py").is_file():
        pytest.skip("brain ausente")
    return Path(b)


def veredito_do_brain(b, tmp):
    (tmp / "scripts").mkdir(parents=True)
    for nome in ("portao.py", "check_title.py"):
        if (b / "scripts" / nome).is_file():
            shutil.copy(b / "scripts" / nome, tmp / "scripts" / nome)
    shutil.copytree(RAIZ / "demo", tmp / "vault", ignore=shutil.ignore_patterns("areas.txt"))
    # o Brain só olha area dentro de <VAULT>/notas: o demo vira o próprio VAULT
    for item in (tmp / "vault").iterdir():
        shutil.move(str(item), str(tmp / item.name))
    (tmp / "vault").rmdir()
    cmd = [sys.executable, str(tmp / "scripts" / "portao.py"), "--auditar", ".", "--json"]
    for c in EM_COMUM:
        cmd += ["--check", c]
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode in (0, 1), r.stdout + r.stderr
    return sorted((f["arquivo"], f["check"]) for f in json.loads(r.stdout)["falhas"])


def veredito_do_template():
    _, falhas = portao.auditar(RAIZ / "demo", checks=set(EM_COMUM))
    return sorted((f.arquivo, f.check) for f in falhas)


def test_mesmo_veredito_nos_checks_em_comum(tmp_path):
    b = brain()
    do_brain, do_template = veredito_do_brain(b, tmp_path), veredito_do_template()
    assert do_template == do_brain


def test_a_comparacao_nao_e_vazia(tmp_path):
    """Equivalência sobre zero falhas seria vácua: cada check em comum tem que reprovar algo."""
    b = brain()
    vistos = {c for _, c in veredito_do_brain(b, tmp_path)}
    assert vistos == set(EM_COMUM)
