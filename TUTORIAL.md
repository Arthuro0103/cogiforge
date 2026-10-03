# Tutorial: usando cada parte da bancada

Este guia vai do zero ao primeiro dia de uso, parte por parte. Em cada uma: **o que fazer** e **o que
você deve ver**. Se o que aparece na sua tela for diferente, é um defeito do guia ou do repo: conta pra
gente.

## O que foi conferido, e o que não foi

| Parte | Como foi conferida (03/10) |
|---|---|
| `instalar.sh`, hook, portão, anel, vazamento, hub | **Rodados num clone limpo**, passo a passo. As saídas abaixo são as reais. |
| `abrir-sessao`, `fechar-sessao` | **Rodadas numa sessão real do Claude Code** num clone limpo. As respostas abaixo são as reais. |
| `conhecer`, `adaptar-skill` | Rodadas até a **primeira pergunta** (são conversas; o resto depende de você). |
| `task-observer`, `claude-corner` | **Não exercitadas ainda.** O que está escrito vem da própria skill. |
| TaskNotes (plugin) e graphify | Seguem a documentação dos projetos. O `graphifyy` foi instalado num ambiente isolado e o `graphify --help` conferido; **o plugin dentro do Obsidian e o `/graphify` sobre um vault não foram rodados aqui.** |

Todas as skills foram testadas na máquina do autor, que tem configurações próprias do Claude Code. Não
provam que funcionam do mesmo jeito na sua. Por isso o guia pede que você anote onde travou.

## 0. Antes de começar

Você precisa de `git`, Python 3.10 ou mais novo, [Obsidian](https://obsidian.md) e o Claude Code.
Funciona em macOS e Linux; no Windows não foi testado. Clone com `git clone` (não baixe o zip: o hook
depende do git).

```sh
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
```

## 1. Instalar o hook

**Faça:**

```sh
sh instalar.sh
```

**Você vê:**

```
OK — hook ativo (core.hooksPath=.githooks) e selftest do anel passou.
Teste você mesmo: crie uma nota sem link em vault/notas/ e rode git commit.
```

O que isso fez: ligou o `core.hooksPath` do git neste clone e provou que o portão das órfãs reprova o
que deve. **Sem este passo o hook existe e não protege**, porque essa configuração do git é local e o
clone não a traz. Se aparecer `ERRO` e `A instalação NÃO foi concluída`, leia a linha acima dele: ela diz
o que faltou (git, Python 3.10, ou estar dentro de um clone).

## 2. Abrir o vault no Obsidian

No Obsidian: *Abrir pasta como cofre* (Open folder as vault) e escolha a pasta **`vault/`** do repo, não
a raiz. O Claude Code você roda na **raiz** do repo, e ele lê e escreve só dentro de `vault/`.

## 3. Instalar o TaskNotes (as tarefas)

O [TaskNotes](https://github.com/callumalpass/tasknotes) é um plugin público do Obsidian (licença MIT,
mantido por uma pessoa de fora deste projeto). Cada tarefa vira uma nota, com calendário e registro de
tempo. **Ele não vem no repo**: você instala pela loja do Obsidian.

**Faça:**

1. Obsidian → *Configurações* → *Plugins da comunidade* (Community plugins) → ligue os plugins da comunidade.
2. *Procurar* (Browse) → busque **TaskNotes** → *Instalar* → *Ativar*.
3. *Configurações* → *TaskNotes* → aba geral: ponha **Default tasks folder** = `tarefas`, e em
   **Identify tasks by** deixe **Tag** com a tag `task`.

**Você deve ver** (pela documentação do plugin; **não conferido aqui dentro do Obsidian**): a tarefa de
exemplo `vault/tarefas/escrever-a-primeira-nota-do-exemplo.md` aparecendo nas telas do plugin, e cada
tarefa criada pela interface virando um arquivo `.md` em `vault/tarefas/`.

> Os nomes das opções acima são os da documentação do plugin na versão 4.13.8. Se estiverem diferentes
> na sua, o que importa é: **pasta das tarefas = `tarefas`** e **tarefa identificada pela tag `task`**.

O formato de uma tarefa (o plugin e as skills escrevem o mesmo):

```yaml
---
tags:
  - task
title: Ligar pro dentista
status: in-progress        # open | in-progress | done
priority: high             # none | low | normal | high
projects:
  - "[[projetos/exemplo-meu-primeiro-projeto/instrucoes|exemplo]]"
---

Pronto quando: consulta marcada.
```

Duas regras da casa sobre tarefas: `tarefas/` **não** é barrada como nota órfã (o plugin cria tarefa sem
pedir link, e barrar aí faria você desinstalar), e o portão **não julga o YAML** dali (o plugin acrescenta
campos próprios, como o tempo registrado). Link morto dentro de uma tarefa continua reprovando.

> Existem também linhas de comando públicas do mesmo autor (`npm install -g tasknotes-cli` e
> `npm install -g mdbase-tasknotes`, as duas MIT). Não são necessárias aqui e não foram testadas.

## 4. Seu primeiro dia: `/conhecer`

**Faça:** com o Claude Code na raiz do repo (`claude`), digite `/conhecer`.

**Você vê** (resposta real, num clone onde o perfil estava vazio):

```
Vamos começar. O perfil está vazio, então é a primeira vez.

Pergunto isso para a bancada servir ao que pesa de verdade, e não a um modelo genérico.

Qual dessas frentes mais te pesa hoje?
1. Trabalho   2. Escola ou estudo   3. Vida pessoal   4. Um projeto específico
Pode escolher uma, juntar várias ou responder com as suas palavras. Também vale "prefiro não dizer".
```

Uma pergunta por vez, cada uma seguindo a sua resposta. O que sai disso:
`vault/_perguntas_sobre_mim.md` preenchido e **propostas** de linhas para `vault/memoria/perfil.md`, com
data e a sua frase literal. Nada entra no perfil sem o seu "sim", e o Claude não deduz o que você não disse.
Resposta curta vale, e "prefiro não dizer" também.

## 5. Criar o seu primeiro projeto

Um projeto é uma pasta em `vault/projetos/` com um arquivo `instrucoes.md` (a **raiz**). Tudo o que nasce
do projeto se liga a ela.

**Faça:**

```sh
cp -R vault/projetos/exemplo-meu-primeiro-projeto vault/projetos/meu-app
```

1. Abra `vault/projetos/meu-app/instrucoes.md` e troque `tipo`, `status` (`ativo`, `pausado` ou
   `encerrado`) e `alvo_declarado` (uma frase: o que existe no mundo quando o projeto der certo).
2. Em `vault/projetos/_index.md`, acrescente uma linha **dentro da tabela** (logo abaixo da última linha
   dela, não depois do parágrafo que vem em seguida):
   `| [[projetos/meu-app/instrucoes\|meu-app]] | ativo | software | Meu primeiro app. |`
3. Rode o hub, que escreve na raiz do projeto a lista de todos os arquivos dele:

```sh
python3 ferramentas/hub.py
python3 ferramentas/hub.py --check
```

**Você vê:**

```
OK         exemplo-meu-primeiro-projeto
OK         meu-app
```

Se esquecer o passo 2, o `--check` responde `FORA DO INDICE meu-app (todo projeto entra em
projetos/_index.md)` e sai com erro. Uma raiz de projeto que ninguém aponta também aparece como órfã
no anel (passo 6).

## 6. Escrever uma nota, e o hook trabalhando

Uma nota é um `.md` em `vault/notas/<area>/`. As áreas válidas estão em `vault/areas.txt` (a pasta tem o
mesmo nome do `area:` da nota). O modelo mínimo está em `vault/CLAUDE.md`.

**a) Uma nota solta é barrada.** Crie `vault/notas/aprendizado/solta.md` com cabeçalho e texto, mas sem
nenhum link, e tente commitar:

```sh
git add vault/notas/aprendizado/solta.md
git commit -m "nota solta"
```

**Você vê:**

```
  ⛔ COMMIT BLOQUEADO — nota deste commit sem nenhuma aresta no grafo

     REPROVA — 1 nota(s) sem nenhum link de entrada ou saída:
        notas/aprendizado/solta.md

     Como consertar: abra a nota e ligue ela a uma nota que EXISTE com um [[wikilink]] no meio do texto
     (onde a conexão é real; bloco de links no rodapé não é o jeito), ou aponte pra ela a partir de uma
     nota existente.
     ...
     Escape consciente: git commit --no-verify
```

**b) Ligue a nota no meio do texto e o commit passa.** Acrescente ao corpo, por exemplo:
`... [[projetos/exemplo-meu-primeiro-projeto/instrucoes|o projeto exemplo]] ganha esta nota.` O link é de
**caminho completo a partir de `vault/`**, e vale onde a conexão é real.

**c) Captura rápida nunca é barrada.** Um arquivo em `vault/inbox/` entra sem link. É de propósito: quem é
barrado na hora de anotar uma ideia desinstala a ferramenta.

**d) Dado pessoal é barrado.** Um arquivo que cita um caminho de máquina (`/Users/<nome>/...`), e-mail,
telefone ou CPF:

```
  ⛔ COMMIT BLOQUEADO — vazamento de dado pessoal no que vai pro commit

     vault/inbox/vazou.md:3: caminho
     1 achado(s) em 1 arquivo(s), de 1 varrido(s)

  Tire o dado do arquivo (a saída acima diz arquivo:linha:tipo, nunca o dado).
```

A saída diz **onde** e **de que tipo**, nunca o dado achado.

**e) A sua lista privada.** Além dos padrões acima, o varredor checa uma lista de termos seus (nomes,
empresas, projetos que não podem aparecer). Ela mora **fora do repo**, em `~/.config/cogiforge/negra.txt`,
um termo por linha. Sem ela, o hook não bloqueia, mas avisa:

```
  NAO_VERIFICADO: lista negra privada ausente — só os padrões genéricos rodaram. Crie
  ~/.config/cogiforge/negra.txt (um termo por linha) para checar a parte privada.
```

Isso significa "a parte privada **não foi conferida**", e nunca "está limpo".

**f) Conferir à mão a qualquer hora:**

```sh
python3 nucleo/portao.py        # links, áreas e cabeçalhos
python3 nucleo/anel.py          # lista as notas órfãs
python3 nucleo/vazamento.py .   # procura dado pessoal
```

O portão responde `N nota(s), 0 reprovam, 0 NAO DEU PRA LER` quando está tudo certo. Ele só confere o
que está **dentro** de `vault/`: um arquivo de fora sai com erro (código 2), nunca como "ok".

## 7. `/abrir-sessao`: onde você parou

**Faça:** diga `abrir sessão do exemplo-meu-primeiro-projeto` (ou o nome do seu projeto), ou use
`/abrir-sessao <projeto>`. Foi com a frase que testamos. Sem nome de projeto ela não dispara.

**Você vê** (resposta real, abreviada, no clone limpo, com a tarefa em andamento criada no passo 3):

```
Projeto: exemplo-meu-primeiro-projeto · status: ativo · alvo: ainda é o texto do modelo (...)

Onde parou: não há onde. vault/memoria/diario/ e vault/memoria/briefings/ não têm nenhum arquivo,
então esta é a primeira sessão.

Ficou aberto (2 tarefas):
- in-progress, prioridade alta: Ligar pro dentista
- open: Escrever a primeira nota ligada ao projeto exemplo

Atenção: A tarefa do dentista aponta para este projeto. Isso é de propósito ou o link ficou errado?

Próximo passo possível (sugestão minha): fazer a tarefa aberta de escrever a primeira nota ligada...
Por onde você quer começar?
```

Ela **só relata o que está nos arquivos**, e onde o disco discorda do que o arquivo afirma ela **pergunta**,
não decide. A sugestão vem marcada como sugestão.

## 8. `/fechar-sessao`: fechar o dia

**Faça:** ao terminar, `/fechar-sessao`. Se alguma coisa te doeu, diga com as suas palavras.

**Você vê** (resposta real, abreviada; dissemos "toda vez que eu crio um projeto novo eu esqueço de pôr no índice" e
pedimos uma tarefa):

```
Arquivos criados (tudo em vault/):
- tarefas/por-projeto-novo-no-indice.md, aberta no projeto meu-app.
- memoria/briefings/2026-10-03-projeto-meu-app.md
- memoria/diario/2026-10-03.md
- memoria/ideias/_dores.md (1 linha acrescentada)

Verificadores: portao.py: 27 notas, 0 reprovam. anel.py --gate: nenhuma órfã.

Achado: a linha do meu-app em projetos/_index.md caiu depois do parágrafo "Status possíveis", fora da
tabela. (...) Quer que eu mova a linha pra dentro da tabela? Depois disso, quer que eu commite?
```

O que ela faz: **diário** do dia, um **briefing** por sessão (com link de caminho completo pra raiz do
projeto no corpo, sem bloco `## Conexões`), **dores** colhidas só da **sua** fala em
`vault/memoria/ideias/_dores.md` (`data | citação literal | fonte`; sem citação literal a linha não entra),
**tarefas** abertas no formato do TaskNotes, e roda o portão e o anel. **Ela só faz commit se você mandar e
nunca dá push.** O que ela criou passou no hook ao ser commitado, sem ajuste.

## 9. `/task-observer`: a bancada aprende com você

**Faça:** durante o trabalho, peça `/task-observer`, ou diga "observa essa sessão".

**O que ela faz** (descrito na skill; **não foi exercitada ainda**): procura três sinais: uma skill que
faltou, um passo repetido três vezes, uma correção que você fez duas vezes. Acrescenta uma linha por
proposta em `vault/memoria/observacoes.md` (data, o que viu, o que propõe). **Só propõe.** Ela nunca
escreve em `perfil.md`, `padroes.md`, `decisoes.md` nem em `vault/notas/`, e **nunca cria skill**: a pauta
é sua, e quem guia a criação é o `/adaptar-skill`.

## 10. `/claude-corner`: o tempo que você está fora

**Faça:** antes de sair, diga "vou sair por uma hora".

**O que ela faz** (descrito na skill; **não foi exercitada ainda**): se você pediu algo antes de sair, esse
pedido é feito **inteiro primeiro**. Depois, no tempo que você disser (no máximo 1h30), o Claude relê as
notas, procura conexões reais, lê as dores e os projetos, e testa ideias num lugar descartável **fora de
`vault/`**. Ele **só propõe**, em `vault/memoria/corner/AAAA-MM-DD-<assunto>.md`: não afirma, não faz merge,
não dá push, não instala nada fora do descartável e não manda mensagem a ninguém. Ao voltar você recebe
um resumo curto e o caminho do arquivo.

## 11. `/adaptar-skill` e as fichas: fazer a sua skill

As skills `artigo`, `conselho`, `ideia-de-produto` e `consultar-notas` **não vêm prontas**: vêm como
**fichas** em `vault/fichas-de-skills/`, que explicam o método por dentro. A ideia é que você decida se
quer uma versão sua e a escreva, em vez de receber uma pronta que talvez não sirva.

**Faça:** `/adaptar-skill`.

**Você vê** (resposta real, abreviada):

```
Alguma skill do catálogo chamou sua atenção? Uma skill é um roteiro que o Claude segue quando você o chama.
Eu pergunto isso pra escolher qual ficha a gente lê junto.

| skill | o que faz |
| conselho | passa uma decisão com custo por vários ângulos que discordam e fecha num veredito |
| artigo | leva uma tese ao texto sem citação inventada |
| ideia-de-produto | acha dor real no que você já escreveu e devolve ideia |
| consultar-notas | responde só com o que suas notas dizem, citando cada nota |

(...) Não li as fichas, e por isso não afirmo qual serviria melhor.
Você pode escolher uma, pedir uma sugestão minha ou dizer "nenhuma serve hoje". (...) Qual delas?
```

O caminho: **ler a ficha juntos → separar o método do que é só do autor → decidir se resolve uma dor
sua → escrever com as suas respostas → testar num caso real → registrar o veredito** em
`vault/memoria/skills-avaliadas.md`. O Claude **nunca escreve a skill por você**, e **"não serve pra mim"
é uma resposta válida** que fica registrada, com o motivo. Sem uma dor sua citada, a resposta é "não agora".

Antes disso, leia `vault/fichas-de-skills/anatomia-de-uma-skill.md` (as sete partes de uma skill e pra que
serve cada uma, em uns 5 minutos).

## 12. Mapa de conexões com o graphify (opcional)

O [graphify](https://github.com/Graphify-Labs/graphify) é um projeto público (licença Apache-2.0) que
transforma uma pasta numa **rede de conceitos** que você pode consultar, em vez de reler os arquivos.
Aqui ele ajuda a achar o que as suas notas têm em comum.

**Faça** (uma vez, no terminal):

```sh
uv tool install graphifyy     # ou: pipx install graphifyy
graphify install              # registra a skill no seu Claude Code
```

O nome do pacote tem **dois `y`**: `graphifyy`. É o que o repositório oficial (Graphify-Labs/graphify)
indica; confira sempre o endereço antes de instalar pacote de terceiros. `graphify install` grava a
skill na pasta de configuração **do seu usuário** (vale pra todos os seus projetos); com
`graphify install --project` ela vai para `.claude/skills/graphify/` deste repo.

Depois, no Claude Code, **na raiz do repo**:

```
/graphify vault
```

**Você vê:** uma pasta `graphify-out/` com `graph.html` (abra no navegador), `GRAPH_REPORT.md` (os
conceitos mais ligados e as conexões que surpreendem) e `graph.json`. Para consultar:
`/graphify query "<pergunta>"`, `/graphify path "A" "B"` e `/graphify explain "conceito"`.

- `graphify-out/` **está no `.gitignore`**: o mapa é gerado das suas notas e não vai para o repo.
- Se `graphify-out/GRAPH_REPORT.md` existir, o Claude lê antes de procurar conexões entre notas.
- Segundo o projeto, o **código** é lido localmente; a leitura semântica de **notas e documentos** passa por
  um modelo (o seu assistente, ou um backend que você configure). Se as suas notas são sensíveis, decida
  isso antes de rodar.
- **Não rodado aqui:** o `/graphify` sobre um vault. Instalamos o pacote num ambiente isolado e o
  `graphify --help` listou os comandos (`install`, `path`, `explain`, entre outros).

## 13. O hook bloqueou meu commit

| O que aparece | O que fazer |
|---|---|
| `nota deste commit sem nenhuma aresta no grafo` | Ligue a nota a outra que **existe**, com `[[caminho/completo\|texto]]` no meio do texto. Ou jogue a captura em `vault/inbox/`. |
| `vazamento de dado pessoal` + `arquivo:linha:tipo` | Tire o dado do arquivo (o hook não mostra o dado, só o lugar). |
| `FORA DO INDICE <projeto>` (no `hub.py`) | Acrescente o projeto como linha dentro da tabela de `vault/projetos/_index.md`. |
| `NAO_VERIFICADO: lista negra privada ausente` | Não é erro. Crie `~/.config/cogiforge/negra.txt` se quiser checar a parte privada. |
| `ILEGIVEL` / código 3 no portão | O arquivo não pôde ser lido (permissão ou não é texto UTF-8). Não é "limpo". |
| `ERRO: ... está fora de vault` | O portão só confere o que está dentro de `vault/`. Copie o arquivo pra dentro. |
| Quero commitar mesmo assim | `git commit --no-verify`. É o escape consciente; use sabendo o que está pulando. |

## 14. Cola rápida

| Pra que | Comando |
|---|---|
| ativar o hook e provar que funciona | `sh instalar.sh` |
| conferir links, áreas e cabeçalhos | `python3 nucleo/portao.py` |
| listar notas órfãs | `python3 nucleo/anel.py` |
| procurar dado pessoal | `python3 nucleo/vazamento.py .` |
| regravar a lista de arquivos de cada projeto | `python3 ferramentas/hub.py` |
| conferir se o hub está em dia | `python3 ferramentas/hub.py --check` |
| rodar os testes do repo | `python3 -m pytest -q` |
| quebrar cada check e exigir teste vermelho | `python3 tests/mutar.py` |

| Skill | Quando |
|---|---|
| `/conhecer` | na primeira vez, e quando quiser atualizar o perfil |
| `/abrir-sessao <projeto>` | ao começar o trabalho num projeto |
| `/fechar-sessao` | ao terminar o dia |
| `/task-observer` | durante o trabalho, pra a bancada propor melhorias |
| `/claude-corner` | quando for sair |
| `/adaptar-skill` | quando quiser uma skill sua a partir de uma ficha |

Algo não bateu com este guia? Anote o passo, o que você esperava e o que apareceu, e mande.
