# CLAUDE.md: cogiforge

Você está na **raiz do repo**. A bancada (as notas, os projetos, a memória da pessoa) mora em `vault/`.
**Antes de agir, leia `vault/CLAUDE.md`**: ele diz como a bancada opera. Este arquivo só traz as leis e
os comandos. Cada lei tem o erro que a originou em [POR-QUE.md](POR-QUE.md).

## As leis

1. **Leia e escreva só dentro de `vault/`.** `nucleo/`, `ferramentas/`, `tests/` e `.githooks/` só mudam se a pessoa pedir.
2. **Não escreva sobre a pessoa o que ela não disse.** Você propõe em `vault/memoria/observacoes.md`; uma linha só entra em `vault/memoria/perfil.md` com o "sim" dela, com data e a frase literal.
3. **O alvo vem antes.** Um item só está processado quando um arquivo que já existia ficou diferente. Nomeie o alvo antes de escrever: `projeto::`, `artigo::`, `pergunta::`, `tarefa::` ou `nenhum`.
4. **Link por caminho completo a partir de `vault/`**, no meio do texto, só onde a conexão é real. Nada de bloco `## Conexões` no rodapé.
5. **Título de nota é uma afirmação de até 10 palavras**, não uma categoria.
6. **Não contorne o hook.** Se o commit foi bloqueado, a mensagem diz o arquivo e o motivo: conserte o arquivo. `--no-verify` só se a pessoa mandar.
7. **Nunca dê `git push`, nem crie remote, nem torne nada público sem a pessoa mandar.**
8. **Dado pessoal não entra no repo** (caminho de máquina, e-mail, telefone, CPF, nomes da lista privada). O hook barra; se barrar, tire o dado.
9. **Tarefa é nota do plugin TaskNotes** em `vault/tarefas/` (`status`: `open`, `in-progress`, `done`; link de caminho completo pro projeto em `projects:`). Detalhes em `vault/CLAUDE.md`.
10. **Se existir `graphify-out/GRAPH_REPORT.md`, leia antes de procurar conexões entre notas.** Ele é gerado: não edite, não commite.
11. **Verificação que não tocou em nada não é OK.** Se você não conseguiu conferir, diga `NAO_VERIFICADO` e por quê, em vez de dizer que está limpo.

## Comandos

| Pra que | Comando |
|---|---|
| ativar o hook e provar que funciona | `sh instalar.sh` |
| conferir links, áreas e frontmatter | `python3 nucleo/portao.py` |
| listar notas órfãs | `python3 nucleo/anel.py` |
| procurar dado pessoal | `python3 nucleo/vazamento.py .` |
| regravar o bloco de arquivos de cada projeto | `python3 ferramentas/hub.py` |
| mapa de conexões (opcional, precisa do graphify instalado) | `/graphify vault` na raiz do repo |
| rodar os testes (precisa do `pytest`; depois do `sh instalar.sh`) | `python3 -m pytest -q` |
| quebrar cada check e exigir teste vermelho | `python3 tests/mutar.py` |

O portão só confere o que está **dentro** de `vault/`: arquivo de fora sai com erro, nunca como OK.

## Skills (em `.claude/skills/`)

`conhecer` (onboarding) · `abrir-sessao <projeto>` · `fechar-sessao` · `task-observer` (só propõe) ·
`claude-corner` (quando a pessoa sai; só propõe) · `adaptar-skill` (a pessoa faz a skill dela a partir
de uma ficha; você não escreve a skill sozinho). As fichas ficam em `vault/fichas-de-skills/`.

## Idioma

Notas e skills estão em português. Responda no idioma da pessoa.
