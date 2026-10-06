---
tipo: explicacao
status: andando
---

# O catálogo diz o que olhar, adaptar ou recusar

Cada linha tem uma **ficha** que explica a skill por dentro, sem o acervo do autor. Ler uma ficha leva uns
10 minutos. O `/adaptar-skill` te guia por ela e por uma pergunta que decide tudo: **isso resolve uma dor
sua?** Recusar é resposta legítima e fica registrada em `vault/memory/skills-avaliadas.md`.

Antes de tudo, leia [[skill-worksheets/anatomy-of-a-skill|a anatomia de uma skill]] (5 minutos).

| skill | o que faz, em uma linha | ficha | dá pra adaptar já? |
|---|---|---|---|
| `conselho` | passa uma decisão com custo por vários ângulos que discordam e fecha num veredito | [[skill-worksheets/council\|conselho]] | sim, é só método |
| `artigo` | leva uma tese ao texto sem citação inventada: lacuna declarada, fonte marcada | [[skill-worksheets/article\|artigo]] | sim, se você escreve textos com fonte |
| `product-idea` | acha dor real no que você já escreveu e devolve ideia, sempre com a citação da dor | [[skill-worksheets/product-idea\|product-idea]] | sim, se você tem material escrito pra varrer |
| `consult-notes` | responde pergunta prática só com o que suas notas dizem, citando a nota de cada afirmação | [[skill-worksheets/consult-notes\|consult-notes]] | sim, se você tem notas sobre o assunto |

**Exemplos já escritos, de graça.** As skills `abrir-sessao`, `fechar-sessao`, `task-observer`,
`claude-corner`, `adaptar-skill` e `conhecer` estão em `.claude/skills/`. Leia a `description` de uma e
compare com a anatomia: é um exemplo de skill pronta e uma referência de formato.

## Como usar

Rode `/adaptar-skill`. Ela pergunta uma coisa por vez, começa pelo que você já contou sobre você, e
termina com a skill escrita e testada por você, ou com um "não serve, porque…" registrado. Nos dois
casos você aprendeu a parte que importa.
