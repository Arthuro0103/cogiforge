#!/bin/sh
# instalar.sh — ativa o hook neste clone e prova que ele funciona. Falha ALTO (rc != 0).
#
# O `core.hooksPath` é config local do git: o clone traz o hook no disco, mas ele só dispara
# depois deste script. Sem isto a proteção existe e não protege.

cd "$(dirname "$0")" || exit 1

falha() {
    echo "" >&2
    echo "ERRO: $*" >&2
    echo "A instalação NÃO foi concluída: o hook não está ativo." >&2
    exit 1
}

command -v git >/dev/null 2>&1 || falha "git não encontrado no PATH."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || falha "isto não é um repositório git. Use 'git clone', não o zip, ou rode 'git init' aqui."
command -v python3 >/dev/null 2>&1 || falha "python3 não encontrado no PATH (precisa ser 3.10 ou mais novo)."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || falha "Python 3.10 ou mais novo é necessário; achei $(python3 -V 2>&1)."
[ -f .githooks/pre-commit ] || falha ".githooks/pre-commit não existe."

chmod +x .githooks/pre-commit || falha "não consegui tornar .githooks/pre-commit executável."
git config core.hooksPath .githooks || falha "não consegui gravar core.hooksPath."

python3 nucleo/anel.py --selftest >/dev/null 2>&1 \
    || { python3 nucleo/anel.py --selftest >&2; falha "o selftest do anel falhou: o gate não pega órfã."; }

echo "OK — hook ativo (core.hooksPath=.githooks) e selftest do anel passou."
echo "Teste você mesmo: crie uma nota sem link em vault/notas/ e rode git commit."
