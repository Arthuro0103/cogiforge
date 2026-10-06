---
tipo: explicacao
status: andando
---

# Uma skill tem sete partes e cada uma tem função

Uma skill é uma **pasta com um arquivo `SKILL.md`** em `.claude/skills/<nome>/`. O Claude Code lê a
`description` de **todas** as skills no começo de cada sessão e só abre o corpo da que casar com o pedido.
Por isso duas coisas valem muito: a `description` decide **quando** a skill dispara, e cada linha dela
**custa contexto em toda sessão**, mesmo nas que nunca disparam.

Pra ver na prática, abra ao lado `.claude/skills/conhecer/SKILL.md` (a mais curta) e procure cada parte.

## As sete partes

| parte | pra que serve | onde achar no `conhecer` |
|---|---|---|
| **1. `description`** | o gatilho: o que faz, as frases que a chamam (`GATILHOS`) e quando **não** disparar (`NÃO dispare`). Máximo de 1024 caracteres | o frontmatter |
| **2. Por que existe** | a dor que originou a skill, de preferência com a frase de quem sentiu. Sem dor, a skill é enfeite | seção "Por que existe" |
| **3. A lei** | poucas regras, cada uma **verificável**: dá pra dizer se foi seguida ou não | seção "A lei" |
| **4. Os passos** | o que fazer, em ordem, com o comando de verdade, dizendo quem faz cada passo (a pessoa, o Claude, um script) | "Os passos" |
| **5. A saída** | onde grava, em que formato, e como se confere | o passo que grava o perfil |
| **6. O modelo de cada agente** | só se a skill abre agentes: quais só leem (modelo menor) e quais decidem (modelo maior) | o `conhecer` não tem: não abre agentes |
| **7. Nunca** | o que a skill não faz. É a parte que mais evita estrago | seção "Nunca" |

## O que separa a skill que se usa da que ninguém chama

1. **A dor tem citação.** Pergunta-teste: *quando foi a última vez que você fez isso à mão?* A dor pode
   ser passada ou **futura**, se você diz por que vai precisar. "Seria legal ter" não conta. Dizer "não
   sei se tenho essa dor" também é resposta.
2. **Foi testada num caso real.** Skill escrita e não rodada é hipótese. Rodar e olhar a saída é metade
   do trabalho.
3. **O gatilho é honesto.** `NÃO dispare` importa tanto quanto `GATILHOS`: skill que dispara à toa
   irrita e gasta contexto.
4. **Diz do que depende.** Se precisa de um arquivo, de uma pasta ou de um programa instalado, isso fica
   no topo; senão quem copia leva uma skill que falha calada.
5. **Pode ser apagada.** Skill que não serviu sai. "Não serviu" é uma resposta boa.

## Adaptar não é copiar

Ao ler a skill de outra pessoa, separe duas camadas:

- **O método**, que serve pra qualquer um: "a dor com citação vem antes da ideia"; "conferir o fato antes
  de julgar"; "várias lentes que discordam entre si".
- **O que é do autor**: as pastas dele, os projetos dele, o jeito dele de decidir, as ferramentas que ele
  instalou. Isso você troca pelo seu ou corta.

A pergunta que faz a adaptação: *"o que nesta skill só funciona porque é o autor?"* Cada resposta vira um
ponto de troca. Quem guia esse trabalho é o `/adaptar-skill`, e o que dá pra olhar está em
[[skill-worksheets/_catalog|_catalog]].
