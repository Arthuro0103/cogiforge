"""Nothing in the repo is in Portuguese by accident.

The repo moved from Portuguese to English in October 2026. This test reads every tracked text file and
every file name, and fails on accented letters, on common Portuguese words, and on the old Portuguese
folder and script names. The few places where Portuguese is deliberate are listed in
tests/pt_allowlist.txt, one `path: reason` per line, so each exception has a reason written next to it.
See docs/TRANSLATING.md for the other direction.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCENTS = re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]")
WORDS = re.compile(r"\b(nao|voce|tambem|entao|isso|quando|porque|ainda|pasta|arquivo|tarefa|tarefas|falha|"
                   r"achado|veredito|orfa|orfas|negra|alvo|nenhum|conserte|rode|nota|notas)\b", re.I)
OLD_NAMES = re.compile(r"(notas|tarefas|projetos|memoria|instrucoes|indice|nucleo|ferramentas|portao|anel|vazamento|"
                       r"instalar|conhecer|abrir|fechar|adaptar|mutar|contagem)", re.I)
BINARY = (".png", ".jpg", ".gif", ".ico")


def allowlist():
    out = {}
    for line in (ROOT / "tests" / "pt_allowlist.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            path, _, reason = line.partition(":")
            assert reason.strip(), f"pt_allowlist.txt: '{path}' has no reason written next to it"
            out[path.strip()] = reason.strip()
    return out


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, cwd=ROOT, check=True).stdout
    return [p for p in out.split("\0") if p]


def test_no_portuguese_in_text_or_in_file_names():
    allowed, problems = allowlist(), []
    for rel in tracked():
        if OLD_NAMES.search(rel) and rel not in allowed:
            problems.append(f"{rel}: the file name is still Portuguese")
        if rel in allowed or rel.endswith(BINARY) or not (ROOT / rel).is_file():
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if ACCENTS.search(line) or WORDS.search(line):
                problems.append(f"{rel}:{n}: {line.strip()[:90]}")
    assert not problems, "Portuguese found (add it to tests/pt_allowlist.txt with a reason, or translate it):\n" + "\n".join(problems[:40])


def test_every_exception_still_exists_and_still_needs_to_be_one():
    """An exception that no longer has any Portuguese in it is a hole in the net: remove it."""
    for rel, reason in allowlist().items():
        path = ROOT / rel
        assert path.is_file(), f"{rel} is in pt_allowlist.txt but does not exist"
        text = path.read_text(encoding="utf-8")
        assert ACCENTS.search(text) or WORDS.search(text) or OLD_NAMES.search(rel) or OLD_NAMES.search(text), \
            f"{rel} has no Portuguese left; take it off the list ({reason})"
