"""Builds a temporary vault from {path: text}."""
from pathlib import Path


def vault(tmp_path, files):
    for rel, text in files.items():
        p = Path(tmp_path) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Path(tmp_path)


def note(area, body="# Title\n\ntext\n"):
    return f"---\narea: {area}\n---\n{body}"
