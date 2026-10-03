---
name: fechar-sessao
description: Fecha o dia de trabalho na bancada. Escreve o diário do dia (vault/memoria/diario/), um briefing por sessão (vault/memoria/briefings/) com link de caminho completo pra raiz do projeto no corpo, colhe dores da fala da pessoa em vault/memoria/ideias/_dores.md, abre tarefa em vault/tarefas/ pro que ficou pendente e roda os verificadores se existirem. Skill nova ou projeto novo saem só como proposta. Commita só se a pessoa mandar e nunca dá push. GATILHOS - "fecha a sessão", "fechar o dia", "/fechar-sessao", "o que fizemos hoje", "resume o dia", "vou parar por hoje". NÃO dispare para resumir conversa curta sem trabalho, para abrir sessão (isso é abrir-sessao) nem para observar processo (isso é task-observer).
---

# fechar-sessao: o que sobrou do dia, escrito antes de esquecer

## Por que existe

Trabalho termina e o contexto some: na sessão seguinte ninguém sabe o que ficou pendente, que
incômodo apareceu, que decisão foi tomada. Quem fecha de memória registra o que lembra, não o que
aconteceu. Fechar com método é transformar a sessão em quatro coisas: diário, briefing, dores, tarefas.

## A lei

1. **A fonte é o que aconteceu, não o que lembro.** Todo número ou fato do briefing vem de comando
   rodado nesta sessão (`git log`, `git diff --stat`, `ls`). Sem comando, escrevo "não medi".
2. **Dor só com fala da pessoa.** Em `_dores.md` entra a frase que ela **escreveu**, entre aspas.
   Frase minha, ou rótulo de opção de menu que ela clicou, não é fala dela: não entra.
3. **Link só se o arquivo existe.** Confira com `test -f` antes de escrever o wikilink. Caminho completo
   a partir de `vault/`, no meio do argumento. **Nunca** um bloco `## Conexões` no rodapé.
4. **Seção sem conteúdo é omitida.** Sessão fraca gera briefing curto. "Nenhuma dor hoje" é resposta válida.
5. **Proponho, não afirmo.** Skill nova, projeto novo, mudança em `perfil.md`, `padroes.md` ou
   `decisoes.md`: saem como proposta no briefing. Quem grava lá é a pessoa.
6. **Sem ordem, sem commit; nunca push.** Pergunte antes de commitar. Esta skill não empurra nada.

## Os passos

### 1. Levantar o que aconteceu (você, o Claude)

```bash
git log --since=midnight --oneline --stat 2>/dev/null | head -40 || true
git status --short
ls -t vault/tarefas/ | head -10
```

Se `git log` não mostrar nada (repo sem commits), diga "não medi: sem commits" e siga pela conversa. Cruze com o que foi dito nela. Descubra o(s) projeto(s) tocado(s): cada um precisa ter
`vault/projetos/<nome>/instrucoes.md`. Se não tiver, diga e pergunte qual é.

### 2. Escrever o briefing, um por sessão (você)

Arquivo `vault/memoria/briefings/AAAA-MM-DD-<slug>.md`, slug curto do assunto:

```yaml
---
tipo: briefing-sessao
data: AAAA-MM-DD
projetos: [<nome>]
---
```

Título: uma afirmação de até 10 palavras sobre o que a sessão produziu. Seções, nesta ordem, **omitindo
as vazias**: *O que aconteceu* (2-3 parágrafos) · *O que foi medido* (comando e número) · *O que a pessoa
corrigiu* (a fala citada) · *O que ficou de pé* (pendência com próximo passo) · *O que pode nascer*
(proposta, com "por que agora"). O link pra raiz entra no corpo, por exemplo:
`... avançou em [[projetos/<nome>/instrucoes|<nome>]] até o ponto X`.

### 3. Escrever ou acrescentar o diário (você)

`vault/memoria/diario/AAAA-MM-DD.md`. Se já existe, **acrescente** uma seção; nunca reescreva o que
está lá. Três a cinco linhas por projeto: o que andou, o que travou, link pro briefing de caminho
completo (`memoria/briefings/...`).

### 4. Colher dores (você)

Releia o que a pessoa **digitou** na sessão: reclamação, gambiarra, coisa feita à mão, "de novo isso".
Acrescente ao fim de `vault/memoria/ideias/_dores.md`, uma por linha, no formato:

```
AAAA-MM-DD | "citação literal dela" | <briefing ou projeto de onde veio>
```

Se o arquivo não existir, não crie: diga que ele pertence à estrutura da bancada e deixe as dores no
briefing, na seção *O que ficou de pé*. Se a citação não for literal, não escreva.

### 5. Abrir tarefa pro que ficou pendente (você)

Uma pendência com próximo passo concreto vira uma tarefa no formato do plugin **TaskNotes**, em
`vault/tarefas/<slug>.md` (o slug sai do título; se o arquivo já existe, acrescente `-2`). Sem ID no nome:
o plugin reconhece tarefa pela tag `task`, não pelo nome do arquivo. `status` é `open`, `in-progress` ou
`done`; `priority` é `none`, `low`, `normal` ou `high`. Pergunte a prioridade se não for óbvia.

```yaml
---
tags:
  - task
title: <verbo no infinitivo + o que>
status: open
priority: normal
projects:
  - "[[projetos/<nome>/instrucoes|<nome>]]"
---
```

O link em `projects` é de **caminho completo** (o portão confere). Corpo: uma linha do que fazer e uma
de "pronto quando".

### 6. Rodar os verificadores, se existirem (um comando cada)

```bash
test -f nucleo/portao.py && python3 nucleo/portao.py || echo "portao.py ainda não existe: pulei"
test -f nucleo/anel.py && python3 nucleo/anel.py --gate || echo "anel.py ainda não existe: pulei"
```

Se algum falhar, mostre a saída e corrija **só o que é seu** (o briefing que acabou de escrever). Não
esconda falha: reporte.

### 7. Entregar e perguntar (você)

Chat, no máximo 8 linhas: caminhos dos arquivos criados, quantas dores colhidas, tarefas abertas,
resultado dos verificadores (ou "pulei: não existem"). Pergunte: *"quer que eu commite?"* Só com sim,
commite os arquivos desta skill, e **sem `git push`**.

## Nunca

- Dar `git push`, nem commitar sem a pessoa mandar.
- Colocar fala minha em `_dores.md`.
- Escrever em `perfil.md`, `padroes.md`, `decisoes.md` ou em `vault/notas/`.
- Criar skill ou projeto: só propor.
- Apagar ou reescrever diário que já existe.
