---
name: adaptar-skill
description: Guia a pessoa a fazer uma skill SUA a partir de uma ficha do catálogo (vault/fichas-de-skills/) - ler a ficha, separar o método do que é só do autor original, decidir se resolve uma dor dela, escrever com as respostas dela, testar num caso real e registrar o veredito em vault/memoria/skills-avaliadas.md. Uma pergunta por mensagem. O Claude nunca escreve a skill sozinho, e "não serve pra mim" é resposta válida que fica registrada. GATILHOS - "/adaptar-skill", "quero uma skill parecida com essa", "essa skill serve pra mim?", "como eu faço uma skill", "o que tem no catálogo de skills". NÃO dispare para USAR uma skill que já existe, para criar skill sem ter olhado uma ficha, nem para o task-observer propor skill (ele só aponta pra cá).
---

# adaptar-skill: aprender a fazer a sua olhando a de outra pessoa

## Por que existe

Skill entregue pronta ensina a **usar**. Skill que a pessoa decide, escreve e testa ensina a **fazer**, e
o que serve muda de uma pessoa pra outra: quem escreve muito e quem toca código brigam por coisas
diferentes. Skill sem dor por trás vira enfeite que gasta contexto em toda sessão. Aqui, a ficha é o
material e a **pessoa** é a autora.

## A lei

1. **Uma pergunta por mensagem.** Nunca uma lista. Diga em uma frase por que pergunta e ofereça 2 a 4
   opções concretas (`AskUserQuestion`), sempre com espaço pra resposta livre.
2. **O Claude não escreve a skill sozinho.** A dor, os gatilhos e o "quando NÃO" saem das respostas
   dela. Eu organizo e formato. Se eu deduzi algo, pergunto.
3. **Ensine enquanto faz.** Em cada passo, uma frase sobre o que aquela parte faz numa skill, com a
   referência em `vault/fichas-de-skills/anatomia-de-uma-skill.md`.
4. **"Não serve" é resposta boa.** Registro com o porquê.
5. **Sem dor, sem skill.** Se ela não diz quando fez isso à mão (ou por que vai precisar), a resposta é
   "não agora": registro e a conversa acaba bem.
6. **Skill sem teste é hipótese.** Rodo num caso real antes de chamar de pronta.
7. **Só no repo dela.** A skill nova vai em `.claude/skills/<nome>/` e nunca sobrescreve outra.

## Os passos

### 1. Antes de perguntar (você, o Claude)

```bash
cat vault/fichas-de-skills/_catalogo.md
cat vault/memoria/skills-avaliadas.md 2>/dev/null     # o que ela já olhou
head -40 vault/memoria/ideias/_dores.md 2>/dev/null   # dores já colhidas
```

Se `skills-avaliadas.md` tem linhas, abra dizendo o que ela já avaliou.

### 2. Escolher qual ficha ler

Mostre o catálogo em uma linha por skill. Pergunte se alguma chamou atenção. Se ela pedir sugestão,
proponha **no máximo duas**, cada uma com a **frase dela** (de `_dores.md`, do perfil ou da conversa)
que sustenta, e diga o que você não leu o bastante pra afirmar. Opção "nenhuma serve hoje": registre
no passo 7 e pare.

### 3. Ler a ficha juntos

Resuma a ficha em 5 linhas. Antes de mostrar a tabela, pergunte: *"nesta skill, o que você acha que é só
do autor e o que é método que qualquer pessoa usaria?"* Depois mostre a tabela da ficha e diga onde ela
acertou e onde faltou.

### 4. A dor

Pergunte: **"quando foi a última vez que você fez isso à mão?"** Peça o caso concreto e anote a data.
A dor pode ser futura se ela disser por quê; "seria legal ter" não conta. Sem dor, vá ao passo 7 com
"não agora". Com dor, siga.

### 5. Escrever, uma parte por mensagem

Sempre a pergunta primeiro, o texto depois, saído da resposta dela:

1. **Por que existe:** *"o que te irritou, em uma frase?"*
2. **Gatilhos:** *"que frases você digitaria pra chamar isso?"* (3 a 5, com as palavras dela)
3. **Quando NÃO disparar:** *"em que situação isso só atrapalharia?"*
4. **Passos:** pra cada passo da ficha, *fica, sai ou troca?* Cada "troca" é algo que dependia do
   autor: pergunte o que entra no lugar.
5. **Saída:** *"onde isso fica gravado e como você sabe que ficou certo?"*
6. **Nunca:** *"o que essa skill jamais deve fazer?"*

Nome: ela escolhe. `description` com até 1024 caracteres, com `GATILHOS` e `NÃO dispare` (confira com
`wc -c`). Monte o `SKILL.md`, **mostre inteiro** e pergunte *"é isso mesmo? o que você tiraria?"*. Só
grave `.claude/skills/<nome>/SKILL.md` depois do sim.

### 6. Testar num caso real

Peça um caso de hoje, não inventado. Rode a skill com ela olhando a saída. Pergunte *"serviu? o que
faltou? o que sobrou?"* e ajuste **uma vez**. Sem caso hoje, registre "não testada".

### 7. Registrar

Acrescente uma linha em `vault/memoria/skills-avaliadas.md` (se não existe, crie só com o cabeçalho):

```markdown
| data | ficha | veredito | dor citada | o que mudou | a sua skill |
|---|---|---|---|---|---|
| AAAA-MM-DD | conselho | serve, adaptada | "travei dois dias entre A e B" | troquei as lentes | .claude/skills/<nome>/SKILL.md |
```

Veredito: **serve, adaptada** · **serve sem mexer** · **serve depois** · **não serve**. A coluna da skill
só é preenchida se o arquivo existe.

## O fecho

Peça que ela diga, com as palavras dela, o que aprendeu sobre fazer skill. Anote o próximo caso em que
a skill deve ser usada.

## Nunca

- Entregar a skill pronta ou escrever partes sem pergunta.
- Criar skill sem ela pedir.
- Dar nota a ela: a pergunta é se a **skill** serve, não se ela acertou.
- Copiar a ficha inteira como se fosse a skill dela.
