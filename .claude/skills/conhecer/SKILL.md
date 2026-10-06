---
name: conhecer
description: Onboarding da bancada. Faz perguntas que seguem o que a pessoa respondeu, uma por vez, e a saída sai da fala dela - preenche vault/_questions_about_me.md e propõe linhas pra vault/memory/profile.md com data e citação literal. Não deduz nada que ela não disse; resposta curta é resposta válida e "prefiro não dizer" também. GATILHOS - "/conhecer", "primeira vez aqui", "me conhece", "atualiza meu perfil", "como eu uso essa bancada". Pode ser sugerida (nunca imposta) quando vault/memory/profile.md estiver vazio ou não existir. NÃO dispare para abrir sessão de projeto (isso é abrir-sessao), para conhecer outra pessoa que não quem está usando, nem para pesquisar a pessoa fora dos arquivos dela.
---

# conhecer: a bancada aprende quem usa

## Por que existe

Uma bancada que ajuda de verdade precisa saber pra que a pessoa a usa: trabalho, escola, vida pessoal,
projetos. Perfil copiado de modelo não serve; ele só presta quando sai de **respostas de verdade**, e as
boas respostas vêm de perguntas que seguem o que a pessoa acabou de dizer.

## A lei

1. **Uma pergunta por mensagem.** Nunca uma lista. A próxima depende da resposta.
2. **Contexto antes das opções.** Uma frase dizendo por que pergunta, depois 2 a 4 opções concretas
   (`AskUserQuestion`), sempre com espaço pra resposta livre.
3. **Pergunta pequena.** "Qual foi a última coisa que você terminou e gostou?" funciona. "Quais são seus
   objetivos de vida?" trava.
4. **Resposta curta ou recusa é resposta.** Não insista, não reformule a mesma pergunta. Anote e siga.
5. **Só a fala dela vai pro perfil.** Suposição minha não entra. Se deduzi algo, eu pergunto.
6. **Citação literal só do que ela digitou.** Se ela clicou numa opção que eu escrevi, registro
   "escolheu a opção X", sem aspas.
7. **De 8 a 15 perguntas.** Pare antes se os blocos abaixo já estão cobertos.
8. **Nada de saúde, família ou relacionamento**, a menos que ela traga e peça pra registrar.

## Os passos

### 1. Antes de perguntar (você, o Claude)

```bash
cat vault/_questions_about_me.md 2>/dev/null
cat vault/memory/profile.md 2>/dev/null
ls vault/projects/ 2>/dev/null
```

Se o perfil já tem linhas, é revisão: abra dizendo o que ele diz e pergunte o que mudou. Se
`_questions_about_me.md` não existe, diga que ele pertence à estrutura da bancada e responda no chat.

### 2. Conversar pelos cinco blocos (a ordem é da conversa)

| bloco | o que descobrir | começo possível |
|---|---|---|
| **pra que usa** | trabalho, escola, pessoal; o que quer organizar primeiro | "qual dessas frentes mais te pesa hoje?" |
| **o que já faz** | o que funciona hoje, que ferramenta usa, o que abandonou | "o que você já anota ou organiza, e onde?" |
| **onde trava** | começar, terminar, decidir, lembrar | "quando um projeto seu parou, parou onde?" |
| **como quer ser ajudada** | passo a passo ou só a direção; cobrança ou autonomia | 3 opções concretas |
| **como quer usar a bancada** | todo dia ou só às vezes; resumo curto ou detalhado | "o que te faria abrir isto amanhã?" |

Quem chega sem nada pra organizar fica mais tempo em **pra que usa** e **onde trava**.

### 3. Preencher `_questions_about_me.md` (você, com o sim dela)

Mostre as respostas organizadas por pergunta do arquivo e pergunte *"posso gravar assim?"*. Só grave
depois do sim, mantendo as palavras dela. Pergunta sem resposta fica em branco.

### 4. Propor linhas pro perfil (você)

Monte as linhas e mostre **antes de gravar**, no formato:

```
AAAA-MM-DD | "frase literal dela" | <bloco> | <o que isto parece dizer, marcado como leitura minha>
```

Se `vault/memory/profile.md` existe, acrescente **só as linhas que ela aprovou**, no fim. Se não
existe, deixe as linhas no chat e avise que o arquivo é da estrutura.

### 5. O fecho (você)

Uma mensagem curta: quais skills combinam com o que ela disse (`abrir-sessao` se trava pra começar,
`fechar-sessao` se perde o fio entre dias), em uma linha cada, com a frase dela que sustenta.
Skill própria só se ela descreveu algo que repete; aí aponte pro `adaptar-skill` e **não crie**.

## Nunca

- Escrever no perfil algo que ela não disse, ou "limpar" a fala dela.
- Gravar sem mostrar antes.
- Avaliar a pessoa: o perfil descreve, não dá nota.
- Escrever em `padroes.md`, `decisoes.md` ou `vault/notes/`.
