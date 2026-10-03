"""Monta um vault temporário a partir de {caminho: texto}."""
from pathlib import Path


def vault(tmp_path, arquivos):
    for rel, texto in arquivos.items():
        p = Path(tmp_path) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")
    return Path(tmp_path)


def nota(area, corpo="# Titulo\n\ntexto\n"):
    return f"---\narea: {area}\n---\n{corpo}"
