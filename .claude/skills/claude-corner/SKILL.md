---
name: claude-corner
description: O canto do Claude. Quando a pessoa avisa que vai sair, o Claude usa o tempo fora (o que ela disser, no máximo 1h30) pra reler as notas, achar conexões reais, ler as dores e os projetos, e testar ideias num lugar descartável fora de vault/. Só propõe, em vault/memory/corner/AAAA-MM-DD-<slug>.md - não afirma, não faz merge, não dá push, não instala nada fora do descartável, não envia mensagem a ninguém. REGRA DE ORDEM - se a pessoa pediu algo antes de sair, o pedido é feito INTEIRO primeiro. GATILHOS - "vou sair", "tô saindo", "volto às X", "fico fora até", "/claude-corner". NÃO dispare para saída de poucos minutos, para tarefa específica que a pessoa quer rodando, nem para decidir entre dois caminhos.
---

# claude-corner: o tempo fora vira proposta

## Por que existe

Enquanto a pessoa está fora, o assistente fica parado, e ela volta ao mesmo ponto. Esse tempo pode ser
usado pra olhar o acervo com calma, e o que ela não teria feito: cruzar notas que não se citam, ler as
dores em fila, testar uma ideia barata. O risco é o assistente agir sem ela. Por isso o produto aqui é
**proposta com procedência**, nunca decisão.

## A lei

1. **O pedido dela vem primeiro e inteiro.** Se ela disse "faz X e vou sair", termino X, **confiro que
   está feito** e só então começo o canto. Se X não pode terminar sem ela, digo isso na hora e o canto
   não começa fingindo que terminou.
2. **Só propõe.** O único lugar de escrita é `vault/memory/corner/`. Não toco em `vault/notes/`,
   `perfil.md`, `padroes.md`, `decisoes.md` nem em `vault/projects/`.
3. **Procedência em cada achado.** Caminho do arquivo e um trecho curto. A fala dela vai entre aspas;
   ideia que nasceu minha leva o rótulo **palpite do Claude**.
4. **Testar só no descartável.** Diretório temporário (`mktemp -d`) ou worktree fora de `vault/`.
   Nada de merge, push, remote novo, mensagem enviada, e-mail, PR, nem instalar pacote fora do descartável.
5. **Tempo tem teto.** O que ela disser; sem prazo dito, **1h30**. Se ela voltar antes, entrego o que
   está pronto.
6. **Link só se o arquivo existe.** Wikilink de caminho completo a partir de `vault/`, no meio do
   argumento. Nunca um bloco `## Conexões` no rodapé.

## Os passos

### 0. Fechar o pedido e ler o relógio (você, o Claude)

Aplique a lei 1. Depois anote o prazo (a hora que ela disse, ou 1h30 a partir de agora).

```bash
ls vault/memory/corner/ 2>/dev/null | tail -5
```

Abra as propostas anteriores, pra não repetir o que ela já viu, adotou ou recusou.

### 1. Varrer o acervo (você)

Cada frente rende **até 5 achados**; leia, não escreva ainda:

- **Conexões:** notas de áreas diferentes que falam da mesma coisa e não se citam
  (`ls vault/notes/`, `grep -rli "<termo>" vault/notes/`).
- **Dores:** `vault/memory/ideas/_pains.md`. Quais se repetem? Alguma tem remédio barato?
- **Projetos:** `vault/projects/_index.md` e as raízes. O que está parado e dá pra adiantar como proposta?
- **Livre:** uma coisa que a pessoa não pediu e que você acha que vale olhar, marcada como palpite.

Se uma frente estiver vazia (pasta inexistente, sem dores), diga "frente vazia" no arquivo. Não preencha.

### 2. Escolher até 3 ideias pra testar (você)

Corte o fraco e o repetido. Fique com as que dá pra testar no tempo que sobrou.

### 3. Testar no descartável (você)

```bash
T=$(mktemp -d) && echo "$T"   # tudo roda aqui dentro, nunca em vault/
```

Rode, meça, escreva o protótipo ali. Registre **o que rodou, a saída e o veredito** (funcionou, não
funcionou, não deu pra medir). Se esbarrar numa decisão que é dela, escreva `ESCALAR: <motivo>` e siga
com o resto.

### 4. Escrever a proposta (você)

`vault/memory/corner/AAAA-MM-DD-<slug>.md`. Abre com um **resumo de até 150 palavras** (os achados mais
fortes). Depois, cada achado traz: o que é, de onde veio (caminho + trecho), o teste, o veredito e o
estado `aberta`. Crie a pasta só se faltar, e só ela.

### 5. Avisar ao voltar (você)

Resumo curto no chat (até 8 linhas) e o caminho do arquivo. Pergunte qual proposta ela quer olhar
primeiro. Nada é commitado a menos que ela mande, e nunca há push.

## Como saber se presta

O resumo cabe em 150 palavras e cada achado tem caminho ao lado. Se, depois de algumas rodadas, tudo
fica `aberta`, o canto está produzindo volume e não valor: encolha a rodada.

## Nunca

- Começar o canto antes de terminar o pedido dela.
- Afirmar algo sobre ela, ou gravar o que ela "provavelmente" quer.
- Fazer merge, push, enviar mensagem, criar remote ou instalar fora do descartável.
- Criar skill ou tarefa: só propor.
