---
name: abrir-sessao
description: Abre uma sessão de trabalho num projeto da bancada. Recebe o NOME de um projeto, lê a raiz dele (vault/projetos/<nome>/instrucoes.md), as últimas entradas do diário e as tarefas abertas dele, e devolve em poucas linhas onde o projeto está e o que a última sessão deixou. Só relata o que está nos arquivos; quando o status do arquivo discorda do que o disco mostra, vira pergunta, nunca veredito. GATILHOS - "abrir sessão do <projeto>", "/abrir-sessao <projeto>", "onde parei no <projeto>", "retomar o <projeto>", "o que falta no <projeto>". NÃO dispare sem nome de projeto (pergunte qual, ou liste vault/projetos/), nem para fechar o dia (isso é fechar-sessao), nem para conhecer a pessoa (isso é conhecer), nem para pergunta sobre código solta.
---

# abrir-sessao: começar sabendo onde parou

## Por que existe

Sessão nova não lembra da anterior. Sem um ponto de partida, a pessoa gasta os primeiros dez minutos
reconstruindo o contexto de cabeça, ou, pior, refaz o que já estava feito. O estado real do projeto está
em arquivos; falta alguém que leia os certos, na ordem certa, e entregue **curto**.

## A lei

1. **Sem nome de projeto, não roda.** Pergunte qual (liste as pastas de `vault/projetos/`). Nunca adivinhe.
2. **Só relata o que leu.** Cada linha do briefing aponta o arquivo de onde veio. Se não leu, não afirma.
3. **Divergência vira pergunta.** Se `status:` do arquivo discorda do disco (ex.: marcado `pausado` com
   commit de ontem), mostre os dois lados e pergunte. Status é decisão da pessoa, não minha.
4. **Briefing curto.** Teto de 12 linhas no chat. Quem precisa ler o arquivo inteiro, abre.
5. **Só leitura.** Esta skill não escreve nada em `vault/`.
6. **Pare no bloco gerado.** Se a raiz tiver um bloco entre marcadores `<!-- hub:inicio` e
   `<!-- hub:fim`, é só lista de links: não leia dali pra baixo.

## Os passos

### 1. Achar o projeto (você, o Claude)

```bash
ls vault/projetos/
test -f vault/projetos/<nome>/instrucoes.md && echo ok
```

Sem a raiz, diga isso e pare: *"não existe vault/projetos/<nome>/instrucoes.md"*. Se o nome bate com
mais de uma pasta, pergunte qual.

### 2. Ler a raiz (você)

Abra `vault/projetos/<nome>/instrucoes.md` até o marcador do hub. Anote do frontmatter: `tipo`, `status`,
`alvo_declarado`. O `alvo_declarado` é o que a pessoa disse querer; o resto é contexto.

### 3. Ler o diário (você)

```bash
ls -t vault/memoria/diario/*.md 2>/dev/null | head -3
```

Abra as três mais recentes e procure só o que fala do projeto (`grep -i "<nome>"` ajuda). Se também
existir briefing recente (`ls -t vault/memoria/briefings/ | head`), veja o mais novo que cita o projeto.
Se a pasta estiver vazia, é a primeira sessão: diga isso.

### 4. Contar as tarefas abertas (um comando)

```bash
grep -l "^projeto: <nome>" vault/tarefas/*.md 2>/dev/null | xargs grep -l "^status: \(open\|doing\)" 2>/dev/null
```

Liste no máximo 5, `doing` primeiro, depois `priority: high`. Se passar de 5, diga quantas ficaram de fora.

### 5. Conferir contra o disco (você)

```bash
git log --oneline -5 -- vault/projetos/<nome> 2>/dev/null   # vazio = sem commits ainda
git status --short vault/projetos/<nome>
```

Compare com o que a raiz afirma (status, datas). Divergência entra no briefing como pergunta.

### 6. Entregar (você)

```
Projeto: <nome>   status: <do arquivo>   alvo: <alvo_declarado, uma linha>
Onde parou:   <1-2 linhas do diário mais recente, com a data>
Ficou aberto: <até 5 tarefas, ID e título>
Atenção:      <divergência do passo 5, em forma de pergunta; omita se não houver>
Próximo passo possível: <uma sugestão, marcada como sugestão minha>
```

Termine perguntando por onde a pessoa quer começar.

## Nunca

- Rodar sem nome de projeto, ou escolher o projeto por conta própria.
- Mudar `status:` ou qualquer campo da raiz.
- Inventar "onde parou" quando o diário está vazio.
- Despejar o arquivo inteiro no chat.
