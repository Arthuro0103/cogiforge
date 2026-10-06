---
name: task-observer
description: Observa uma sessão de trabalho e SÓ PROPÕE melhorias de processo, acrescentando em vault/memory/observacoes.md (data, o que viu, o que propõe). Procura três sinais - uma skill que faltou, um passo repetido três vezes, uma correção que a pessoa fez duas vezes. Nunca escreve em perfil.md, padroes.md, decisoes.md nem em vault/notes/, e nunca cria skill: a pauta de skills é da pessoa, e quem guia a criação é o adaptar-skill. É a metade "melhora comigo" da bancada. GATILHOS - "/task-observer", "observa essa sessão", "o que eu repito muito?", "o que dava pra automatizar?", "tem algo pra melhorar no meu processo?". NÃO dispare para executar a tarefa em si, para fechar o dia (isso é fechar-sessao), nem para criar skill (isso é adaptar-skill).
---

# task-observer: ver o processo enquanto ele acontece

## Por que existe

Quem trabalha sempre do mesmo jeito deixa de ver o próprio jeito: o passo que repete todo dia, a
correção que dá ao assistente pela terceira vez, a skill que ajudaria e ninguém escreveu. Quem faz
o trabalho está ocupado demais pra anotar. Alguém de fora precisa olhar e **só apontar**, sem mexer.

## A lei

1. **Só propõe.** O único arquivo que esta skill escreve é `vault/memory/observacoes.md`, e só
   **acrescentando** no fim. Nunca reescreve nem apaga linha anterior.
2. **Três sinais, nada além.** (a) uma skill que faltou, (b) um passo feito à mão 3 vezes ou mais,
   (c) uma correção que a pessoa fez 2 vezes ou mais. Sem o número, não vira observação.
3. **Cada observação traz a evidência.** Onde aconteceu (arquivo, data ou trecho curto da fala) e a
   contagem. "Parece que..." sem evidência não entra.
4. **Não afirma sobre a pessoa.** Escrevo "o passo X apareceu 3 vezes", nunca "ela é desorganizada".
   `perfil.md`, `padroes.md` e `decisoes.md` são afirmações sobre ela: eu não escrevo lá.
5. **Nunca cria skill.** Se o sinal é "faltou skill", a observação diz isso e aponta pro `adaptar-skill`.
   A pessoa decide se e quando.
6. **Não mexe em `vault/notes/`.** Nota é o acervo dela.
7. **Observar não interrompe.** Não pare o trabalho pra comentar; registre e mostre no fim, ou quando pedirem.

## Os passos

### 1. Antes (você, o Claude)

```bash
tail -30 vault/memory/observacoes.md 2>/dev/null
```

Leia o que já foi observado, pra não repetir. Se uma observação antiga voltou a acontecer, **cite a data
dela** e some à contagem em vez de abrir outra.

### 2. Durante a sessão (você)

Mantenha uma contagem mental simples de: comandos ou passos repetidos, correções que a pessoa fez
("não, assim não", "de novo", "já te falei"), e pedidos que não tinham skill pra atender. Anote a
evidência na hora, em duas linhas, para não depender da memória no fim.

### 3. Filtrar (você)

No fim do bloco de trabalho, descarte o que não bate com os três sinais ou não tem contagem. Tenha
no máximo **3 observações por sessão**: mais que isso é ruído, e a pessoa para de ler.

### 4. Acrescentar (você)

Se `vault/memory/observacoes.md` não existe, avise que ele pertence à estrutura e mostre as
observações no chat, sem criar o arquivo. Se existe, acrescente no fim:

```markdown
## AAAA-MM-DD

- **O que vi:** <fato, com a contagem e onde aconteceu>
- **Sinal:** skill que faltou | passo repetido | correção repetida
- **O que proponho:** <uma frase; se for skill, "levar ao /adaptar-skill">
- **Estado:** aberta
```

Se a observação diz respeito a um projeto, ponha um wikilink de caminho completo na frase, no meio
do texto (`[[projects/<nome>/instructions|<nome>]]`), e só depois de conferir que o arquivo existe.

### 5. Mostrar (você)

Chat: as observações do dia em uma linha cada, e a pergunta *"alguma dessas vale virar algo?"*. Se a
resposta for sobre skill, passe pro `adaptar-skill`; não comece a escrever.

### 6. Fechar o ciclo (a pessoa)

Só a pessoa muda o campo **Estado** (`aberta`, `adotada`, `recusada`). Recusar é resposta boa:
na próxima rodada, não proponha de novo a mesma coisa sem uma contagem nova.

## Nunca

- Escrever em `perfil.md`, `padroes.md`, `decisoes.md` ou `vault/notes/`.
- Criar, editar ou instalar uma skill.
- Registrar observação sem contagem e evidência.
- Repetir proposta que a pessoa recusou, sem fato novo.
