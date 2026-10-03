"""Ponta a ponta: um clone temporário, `sh instalar.sh`, e commits de verdade."""
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
LEAK = "/Users/" + "fulano"  # montado aqui para este arquivo não se acusar


def sh(cwd, *cmd, env=None):
    import os
    return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "VAZAMENTO_NEGRA": str(cwd / "sem-lista.txt"), **(env or {})})


@pytest.fixture
def clone(tmp_path):
    repo = tmp_path / "clone"
    repo.mkdir()
    for item in ("nucleo", ".githooks", "instalar.sh", "vault", ".gitignore"):
        origem = RAIZ / item
        if origem.is_dir():
            shutil.copytree(origem, repo / item, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(origem, repo / item)
    sh(repo, "git", "init", "-q")
    sh(repo, "git", "config", "user.name", "teste")
    sh(repo, "git", "config", "user.email", "teste@example.com")
    r = sh(repo, "sh", "instalar.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    sh(repo, "git", "add", "-A")
    r = sh(repo, "git", "commit", "-q", "-m", "esqueleto")
    assert r.returncode == 0, r.stdout + r.stderr
    return repo


def commitar(repo, rel, texto, *extra):
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(texto, encoding="utf-8")
    sh(repo, "git", "add", rel)
    return sh(repo, "git", "commit", "-q", "-m", "x", *extra)


ORFA = "---\narea: vida\n---\n# Nota sem aresta\n\nTexto sem link.\n"


def test_instalar_ativa_o_hookspath(clone):
    assert sh(clone, "git", "config", "--get", "core.hooksPath").stdout.strip() == ".githooks"


def test_orfa_bloqueia_o_commit_e_ensina(clone):
    r = commitar(clone, "vault/notas/vida/orfa.md", ORFA)
    assert r.returncode == 1
    assert "COMMIT BLOQUEADO" in r.stdout + r.stderr and "Como consertar" in r.stdout + r.stderr


def test_com_o_wikilink_o_commit_passa(clone):
    r = commitar(clone, "vault/notas/vida/orfa.md", ORFA + "\nVolta ao [[_indice]].\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_sem_hookspath_o_hook_nao_dispara(clone):
    sh(clone, "git", "config", "--unset", "core.hooksPath")
    assert commitar(clone, "vault/notas/vida/orfa.md", ORFA).returncode == 0


def test_no_verify_e_o_escape_consciente(clone):
    assert commitar(clone, "vault/notas/vida/orfa.md", ORFA, "--no-verify").returncode == 0


def test_inbox_nunca_e_barrado(clone):
    assert commitar(clone, "vault/inbox/ideia.md", "# ideia solta, sem link\n").returncode == 0


def test_orfa_de_fora_do_commit_so_avisa(clone):
    (clone / "vault/notas/vida/velha.md").write_text(ORFA, encoding="utf-8")  # não entra no stage
    r = commitar(clone, "vault/notas/vida/ok.md", "---\narea: vida\n---\n# Ligada\n\n[[_indice]]\n")
    assert r.returncode == 0 and "AVISO" in r.stdout + r.stderr and "velha.md" in r.stdout + r.stderr


def test_vazamento_no_stage_bloqueia_qualquer_arquivo(clone):
    r = commitar(clone, "docs/nota.txt", f"abri {LEAK}/x\n")
    assert r.returncode == 1 and "vazamento" in (r.stdout + r.stderr).lower()
    assert "fulano" not in r.stdout + r.stderr


def test_vazamento_em_md_do_vault_tambem_bloqueia(clone):
    r = commitar(clone, "vault/notas/vida/v.md", f"---\narea: vida\n---\n# V\n\n[[_indice]] {LEAK}\n")
    assert r.returncode == 1


def test_sem_lista_privada_avisa_nao_verificado_e_nao_bloqueia(clone):
    r = commitar(clone, "docs/ok.txt", "limpo\n")
    assert r.returncode == 0 and "NAO_VERIFICADO" in r.stdout + r.stderr


def test_instalacao_incompleta_falha_alto(clone):
    (clone / "nucleo" / "anel.py").unlink()
    r = commitar(clone, "docs/ok.txt", "limpo\n")
    assert r.returncode == 1 and "instalar.sh" in r.stdout + r.stderr


# ---- instalar.sh falha alto ----------------------------------------------------

def test_instalar_fora_de_repo_git_falha(tmp_path):
    for item in ("nucleo", ".githooks", "instalar.sh"):
        o = RAIZ / item
        shutil.copytree(o, tmp_path / item, ignore=shutil.ignore_patterns("__pycache__")) if o.is_dir() else shutil.copy(o, tmp_path / item)
    r = sh(tmp_path, "sh", "instalar.sh", env={"GIT_CEILING_DIRECTORIES": str(tmp_path.parent)})
    assert r.returncode != 0 and "repositório git" in r.stdout + r.stderr


def test_instalar_com_selftest_quebrado_falha(clone):
    sh(clone, "git", "config", "--unset", "core.hooksPath")
    (clone / "nucleo" / "anel.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    r = sh(clone, "sh", "instalar.sh")
    assert r.returncode != 0 and "selftest" in (r.stdout + r.stderr).lower()


def test_instalar_com_python_antigo_falha(clone, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python3").write_text("#!/bin/sh\n[ \"$1\" = \"-c\" ] && exit 1\nexit 0\n", encoding="utf-8")
    (fake / "python3").chmod(0o755)
    import os
    r = sh(clone, "sh", "instalar.sh", env={"PATH": f"{fake}:{os.environ['PATH']}"})
    assert r.returncode != 0 and "3.10" in r.stdout + r.stderr
