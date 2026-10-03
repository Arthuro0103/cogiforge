# CLAUDE.md: como esta bancada opera

Bancada criativa: trabalho, escola e vida pessoal no mesmo lugar. Você (Claude) organiza projetos,
ideias e tarefas, ajuda a escrever e planejar, e melhora junto com quem usa. O Obsidian abre `vault/`;
você roda na raiz do repo e lê e escreve **só dentro de `vault/`**.

## Primeira vez

1. A pessoa responde `_perguntas_sobre_mim.md` (vazio no começo). Nada é inventado por você.
2. Crie o projeto: copie `projetos/exemplo-meu-primeiro-projeto/` para `projetos/<nome>/`, edite o
   frontmatter (`tipo`, `status`, `alvo_declarado`) e acrescente a linha em `projetos/_index.md`.
3. Rode `python3 ferramentas/hub.py` para o projeto listar seus arquivos.

## Pastas

`inbox/` captura bruta · `notas/<area>/` notas processadas (a pasta é definida pelo `area:` da nota;
as áreas são as que a pessoa configurar) · `projetos/<nome>/instrucoes.md` raiz de cada projeto ·
`memoria/` o que a pessoa disse (`perfil`, `padroes`, `decisoes`, `ideias/_dores.md`) · `tarefas/`
um arquivo por tarefa (`status: open|doing|done`, `priority`, `projeto`).

## O alvo vem antes

**Um item só está processado quando um arquivo que já existia ficou diferente.** A nota é o rastro,
não o produto. Medido: nota que nasce de conversa chegou a um arquivo de projeto em 4 de 4; a que
nasceu de arquivo solto, em 0 de 43. Por isso:

1. Nomeie o alvo **antes** de escrever: `projeto::` · `artigo::` · `pergunta::` · `tarefa::` · `nenhum`.
   `nenhum` é resposta legítima; o item fica no inbox com data, não é apagado.
2. Escreva a nota e o diff no alvo no mesmo commit.
3. Conversa direta vale mais que inbox. Inbox é fallback.

## Regras de escrita

- Título é uma afirmação de até 10 palavras, nunca uma categoria.
- Link por caminho completo a partir de `vault/`: `[[projetos/exemplo-meu-primeiro-projeto/instrucoes|exemplo]]`. Só existe quando a conexão é real.
- **Sem bloco `## Conexões` no rodapé.** O link entra no corpo, no meio do argumento.
- Arquivo novo que fala de um projeto leva um wikilink para a raiz dele.
- Nada afirma coisa sobre a pessoa que ela não disse. Você **propõe** em `memoria/observacoes.md`; só entra em `memoria/` com o "sim" dela, com data e citação literal.

## Primeira nota

Modelo mínimo (a lista de `area:` é da pessoa; a pasta é `notas/<area>/`):

```
---
tipo: nota
area: estudos
projeto: exemplo-meu-primeiro-projeto
data: 2026-10-03
---
# Título que é uma afirmação de até dez palavras

Corpo com o argumento. O link entra aqui, no meio:
[[projetos/exemplo-meu-primeiro-projeto/instrucoes|o projeto]] muda por causa disto.
```

Depois de gravar, rode `python3 ferramentas/hub.py`: nota em `projetos/<nome>/` entra sozinha no
bloco da raiz; nota em `notas/` só aparece lá pelo link no corpo.

## Quando usar cada skill

| skill | quando |
|---|---|
| `abrir-sessao` | ao começar: lê o estado, drena o inbox, mostra o que está aberto |
| `fechar-sessao` | ao terminar: diário, briefing, dores colhidas, tarefas abertas |
| `task-observer` | durante o trabalho: anota correções e padrões para a bancada melhorar |
| `claude-corner` | quando você tiver uma proposta própria para a bancada |
| `conhecer` | depois que a pessoa responde perguntas: propõe o que enxergou |
| `adaptar-skill` | ao trazer skill de fora: veredito do que serviu e por quê |

## Nunca

Gravar fora de `vault/`. Apagar nota sem pedido. Preencher `memoria/` sem fala da pessoa.
