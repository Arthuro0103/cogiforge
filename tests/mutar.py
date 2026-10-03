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
    "portao": dict(arquivo="nucleo/portao.py", suite=["tests/test_portao.py", "tests/test_demo.py"], textos=[
        ("area: pasta ≠ area passa", 'if area != esperada:', 'if False:'),
        ("frontmatter de tarefas é julgado pelo subconjunto", ' or Path(n.rel).parts[0] in PASTAS_DO_PLUGIN', ''),
        ("arquivo de fora do vault passa", 'arq.resolve().relative_to(vault.resolve())', 'arq.resolve().relative_to(arq.resolve())'),
        ("area: fora da lista passa", 'if area not in areas.values():', 'if False:'),
        ("area: pasta desconhecida passa", 'if esperada is None:', 'if False:'),
        ("area: campo ausente passa", 'if area is None or not str(area).strip():', 'if False:'),
        ("area: nota solta passa", 'if len(partes) < 3:', 'if False:'),
        ("area: conta 2x com frontmatter", 'if n.fm_erro:\n        return []  # já reprovou', 'if False:\n        return []  # já reprovou'),
        ("area: vale fora de notas/", 'if partes[0] != "notas":', 'if False:'),
        ("fm: tabulação aceita", r'if "\t" in s[:len(s) - len(s.lstrip())]:', 'if False:'),
        ("fm: dois-pontos sem aspas aceito", 'if ": " in v or v.endswith(":"):', 'if False:'),
        ("fm: aspas abertas aceitas", 'if len(v) < 2 or v[-1] != v[0]:', 'if False:'),
        ("fm: lista aberta aceita", 'if not v.endswith("]"):', 'if False:'),
        ("fm: texto em bloco aceito", 'if v[:1] in "{|>&*!%@`":', 'if False:'),
        ("fm: comentário no fim ficaria no valor", r'v = re.sub(r"\s+#.*$", "", v)', 'v = v'),
        ("fm: mapa aninhado aceito", 'if not item or ultima is None:', 'if False:'),
        ("fm: item sobre escalar aceito", 'if not isinstance(d[ultima], list):', 'if False:'),
        ("fm: linha sem chave aceita", 'if not m:\n                raise', 'if False:\n                raise'),
        ("fm: aberto sem fechar passa", 'return None, (1, "abre com --- e nunca fecha")', 'return None, None'),
        ("link: camada relativa", 'if r.lower() in self.caminhos:', 'if False:'),
        ("link: sufixo de caminho", 'if baixo.endswith("/" + c.lower()):', 'if False:'),
        ("link: nome casa só com caixa exata", 'n = alvo.lower() if tem_ext else alvo.lower() + ".md"', 'n = alvo if tem_ext else alvo + ".md"'),
        ("mascara: cerca fecha cedo", 'if m and m.group(1)[0] == cerca[0] and len(m.group(1)) >= cerca[1] and linha.strip() == m.group(1):', 'if m:'),
        ("mascara: inline vira link", 'out.append(INLINE.sub(lambda x: " " * len(x.group(0)), linha))', 'out.append(linha)'),
        ("link: âncora fica no alvo", 'return re.split(r"[#^]", alvo, maxsplit=1)[0].strip()', 'return alvo.strip()'),
        ("alvo: nenhum vira morto", ' or a.lower() == "nenhum":', ':'),
        ("alvo: nome com caminho casa por sufixo", 'or ("/" not in a and idx.achar(a, n.rel) is not None)', 'or idx.achar(a, n.rel) is not None'),
        ("alvo: nome puro nunca resolve", 'or ("/" not in a and idx.achar(a, n.rel) is not None)', ''),
        ("varre pastas de ferramenta (índice)", 'dirs[:] = sorted(d for d in dirs if d not in IGNORAR_DIRS)\n            for fn in sorted(nomes):', 'dirs[:] = sorted(dirs)\n            for fn in sorted(nomes):'),
        ("varre pastas de ferramenta (coleta)", 'dirs[:] = sorted(d for d in dirs if d not in IGNORAR_DIRS)\n            achados +=', 'dirs[:] = sorted(dirs)\n            achados +='),
        ("ilegível não sai 3", 'return 3 if ileg else (1 if falhas else 0)', 'return 1 if falhas else 0'),
        ("falha não sai 1", 'return 3 if ileg else (1 if falhas else 0)', 'return 3 if ileg else 0'),
        ("--check não filtra", 'if not checks or f.check in checks', 'if True'),
        ("check desconhecido aceito", 'or (args.check and set(args.check) - nomes)', ''),
        ("não-utf8 lido como texto", 'except (OSError, UnicodeDecodeError) as e:', 'except OSError as e:'),
        ("link-partido conta o link inteiro", 'if "[[" in resto:', 'if "[[" in linha:'),
    ]),
    "anel": dict(arquivo="nucleo/anel.py", suite=["tests/test_anel.py", "tests/test_demo.py"], textos=[
        ("inbox e tarefas deixam de ser isentos", 'DEPOSITOS = ("inbox", "tarefas")', 'DEPOSITOS = ()'),
        ("tarefas deixa de ser isento", 'DEPOSITOS = ("inbox", "tarefas")', 'DEPOSITOS = ("inbox",)'),
        ("inbox deixa de ser isento", 'DEPOSITOS = ("inbox", "tarefas")', 'DEPOSITOS = ("tarefas",)'),
        ("inbox isento por prefixo", 'rel == d or rel.startswith(d + "/")', 'rel.startswith(d)'),
        ("autolink é aresta", 'if r and r != rel and r.endswith(".md"):', 'if r and r.endswith(".md"):'),
        ("link pra imagem é aresta", 'if r and r != rel and r.endswith(".md"):', 'if r and r != rel:'),
        ("entrada não conta", '                grau[r] += 1\n', '                pass\n'),
        ("saída não conta", '                grau[rel] += 1\n', '                pass\n'),
        ("link markdown não é aresta", ' + [unquote(m) for m in MDLINK.findall(texto)]', ''),
        ("link markdown sem unquote", 'unquote(m) for m in', 'm for m in'),
        ("código vira aresta", 'texto = mascarar(Path(vault, rel).read_bytes().decode("utf-8", errors="replace"))', 'texto = Path(vault, rel).read_bytes().decode("utf-8", errors="replace")'),
        ("stage sem NFC", 'if nfc(r) in no_commit', 'if r in no_commit'),
        ("stage: aviso some", 'if fora:', 'if False:'),
        ("stage: git ausente vira ok", 'print("NAO_VERIFICADO: não consegui ler o stage do git', 'return 0; print("NAO_VERIFICADO: não consegui ler o stage do git'),
        ("vault inexistente vira ok", 'if not Path(vault).is_dir():\n        print(f"NAO_VERIFICADO', 'if False:\n        print(f"NAO_VERIFICADO'),
        ("mensagem não ensina", 'Como consertar: abra', 'abra'),
        ("selftest sempre ok", 'return 1 if falhou else 0', 'return 0'),
        ("selftest não planta órfã", r'esc("solta.md", "nenhum link aqui\n")', r'esc("solta.md", "ligada a [[a]]\n")'),
        ("--stage ignorado no CLI", 'return gate(args.vault, so_stage=args.stage)', 'return gate(args.vault)'),
    ]),
    "hook": dict(arquivo=".githooks/pre-commit", suite=["tests/test_hook_e2e.py"], textos=[
        ("anel não roda", 'python3 nucleo/anel.py --vault vault --gate --stage', 'true'),
        ("anel olha o vault inteiro", '--gate --stage', '--gate'),
        ("filtro .md some", "grep -q '\\.md$'", "grep -q 'ZZZ'"),
        ("anel não bloqueia", "head -20\n        bloqueado=1\n    elif", "head -20\n    elif"),
        ("aviso do anel some", "elif grep -q '^AVISO' \"$saida\"; then", "elif false; then"),
        ("vazamento não roda", 'python3 nucleo/vazamento.py --staged', 'true'),
        ("vazamento não bloqueia", "    bloqueado=1\nelif", "elif"),
        ("NAO_VERIFICADO some", "elif grep -q 'NAO_VERIFICADO' \"$saida\"; then", "elif false; then"),
        ("saída sempre 0", '[ "$bloqueado" -eq 0 ] || {', 'true || {'),
        ("instalação incompleta passa", 'if [ ! -f "$f" ]; then', 'if false; then'),
    ]),
    "instalar": dict(arquivo="instalar.sh", suite=["tests/test_hook_e2e.py"], textos=[
        ("não ativa o hooksPath", 'git config core.hooksPath .githooks || falha', 'true || falha'),
        ("python antigo passa", '    || falha "Python 3.10 ou mais novo é necessário; achei $(python3 -V 2>&1)."', '    || true'),
        ("selftest quebrado passa", '    || { python3 nucleo/anel.py --selftest >&2; falha "o selftest do anel falhou: o gate não pega órfã."; }', '    || true'),
        ("fora de repo git passa", "    || falha \"isto não é um repositório git. Use 'git clone', não o zip, ou rode 'git init' aqui.\"", '    || true'),
    ]),
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
