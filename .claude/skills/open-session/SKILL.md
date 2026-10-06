---
name: abrir-sessao
description: Abre uma sessão de trabalho num projeto da bancada. Recebe o NOME de um projeto, lê a raiz dele (vault/projects/<nome>/instructions.md), as últimas entradas do diário e as tarefas abertas dele, e devolve em poucas linhas onde o projeto está e o que a última sessão deixou. Só relata o que está nos arquivos; quando o status do arquivo discorda do que o disco mostra, vira pergunta, nunca veredito. GATILHOS - "abrir sessão do <projeto>", "/abrir-sessao <projeto>", "onde parei no <projeto>", "retomar o <projeto>", "o que falta no <projeto>". NÃO dispare sem nome de projeto (pergunte qual, ou liste vault/projects/), nem para fechar o dia (isso é fechar-sessao), nem para conhecer a pessoa (isso é conhecer), nem para pergunta sobre código solta.
---

# abrir-sessao: começar sabendo onde parou

## Por que existe

Sessão nova não lembra da anterior. Sem um ponto de partida, a pessoa gasta os primeiros dez minutos
reconstruindo o contexto de cabeça, ou, pior, refaz o que já estava feito. O estado real do projeto está
em arquivos; falta alguém que leia os certos, na ordem certa, e entregue **curto**.

## A lei

1. **Sem nome de projeto, não roda.** Pergunte qual (liste as pastas de `vault/projects/`). Nunca adivinhe.
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
ls vault/projects/
test -f vault/projects/<nome>/instructions.md && echo ok
```

Sem a raiz, diga isso e pare: *"não existe vault/projects/<nome>/instructions.md"*. Se o nome bate com
mais de uma pasta, pergunte qual.

### 2. Ler a raiz (você)

Abra `vault/projects/<nome>/instructions.md` até o marcador do hub. Anote do frontmatter: `tipo`, `status`,
`declared_target`. O `declared_target` é o que a pessoa disse querer; o resto é contexto.

### 3. Ler o diário (você)

```bash
ls -t vault/memory/diario/*.md 2>/dev/null | head -3
```

Abra as três mais recentes e procure só o que fala do projeto (`grep -i "<nome>"` ajuda). Se também
existir briefing recente (`ls -t vault/memory/briefings/ | head`), veja o mais novo que cita o projeto.
Se a pasta estiver vazia, é a primeira sessão: diga isso.

### 4. Contar as tarefas abertas (um comando)

```bash
for f in vault/tasks/*.md; do
  grep -q "projects/<nome>/instructions" "$f" 2>/dev/null && grep -q -E "^status: *(open|in-progress)" "$f" 2>/dev/null && echo "$f"
done
```

Liste no máximo 5, `in-progress` primeiro, depois `priority: high`, mostrando o `title:` de cada uma. Se
passar de 5, diga quantas ficaram de fora.

### 5. Conferir contra o disco (você)

```bash
git log --oneline -5 -- vault/projects/<nome> 2>/dev/null   # vazio = sem commits ainda
git status --short vault/projects/<nome>
```

Compare com o que a raiz afirma (status, datas). Divergência entra no briefing como pergunta.

### 6. Entregar (você)

```
Projeto: <nome>   status: <do arquivo>   alvo: <declared_target, uma linha>
Onde parou:   <1-2 linhas do diário mais recente, com a data>
Ficou aberto: <até 5 tarefas, título e status>
Atenção:      <divergência do passo 5, em forma de pergunta; omita se não houver>
Próximo passo possível: <uma sugestão, marcada como sugestão minha>
```

Termine perguntando por onde a pessoa quer começar.

## Nunca

- Rodar sem nome de projeto, ou escolher o projeto por conta própria.
- Mudar `status:` ou qualquer campo da raiz.
- Inventar "onde parou" quando o diário está vazio.
- Despejar o arquivo inteiro no chat.
