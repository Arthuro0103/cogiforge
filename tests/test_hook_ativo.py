"""O hook versionado só protege se estiver ATIVO.

`core.hooksPath` é config LOCAL do git: num clone novo o arquivo `.githooks/pre-commit` existe no
disco e NÃO dispara. Este teste é o alarme desse caso: fica vermelho até alguém rodar
`sh instalar.sh`, e volta a ficar vermelho se alguém rodar `git config --unset core.hooksPath`.
"""
import os
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_hookspath_aponta_pro_githooks():
    r = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=RAIZ, capture_output=True, text=True)
    assert r.stdout.strip() == ".githooks", (
        f"core.hooksPath = {r.stdout.strip()!r}, esperado '.githooks'. O hook existe no disco mas NÃO dispara. "
        "Rode: sh instalar.sh")


def test_o_hook_existe_e_e_executavel():
    hook = RAIZ / ".githooks" / "pre-commit"
    assert hook.is_file() and os.access(hook, os.X_OK)


def test_o_hook_chama_o_anel_e_o_vazamento():
    texto = (RAIZ / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "nucleo/anel.py" in texto and "--gate --stage" in texto
    assert "nucleo/vazamento.py" in texto and "--staged" in texto
