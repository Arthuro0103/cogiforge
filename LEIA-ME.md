# cogiforge

*cogi ergo sum*: uma bancada criativa pra sua cabeça. Um segundo cérebro em **Obsidian + Claude Code**
que guarda trabalho, escola e vida pessoal no mesmo lugar, **organiza seus projetos, ideias e tarefas,
te ajuda a escrever e planejar, e melhora junto com você** conforme você usa.

> **Estado: alpha (v0.x).** Saiu do vault de trabalho do autor e, até agora, só o autor usou. Se você
> é o primeiro de fora, o mais útil que pode mandar é onde travou. English: [README.md](README.md).

## Pra quem é

Pra quem quer um lugar só pro que está fazendo, seja trabalho, escola, projeto de fim de semana ou a
própria cabeça, e quer que ele **ajude de verdade** em vez de só guardar. Não é um app: é uma pasta de
notas (o Obsidian abre) mais um Claude Code que sabe operar essa pasta.

## O que vem nela

| Peça | O que faz |
|---|---|
| `vault/` | A bancada. `inbox/` pra captura rápida, `notas/` pra nota processada, `projetos/` com um arquivo raiz por projeto, `memoria/` pro que **você** disse, `tarefas/` pras tarefas. Abra essa pasta no Obsidian. |
| `/conhecer` | O onboarding. Pergunta uma coisa por vez, cada pergunta seguindo a sua resposta, e grava o que **você disse**, com data e citação. Não deduz nada. |
| `/abrir-sessao <projeto>` | Começa o trabalho num projeto: lê a raiz dele, o diário recente e as tarefas abertas, e diz onde você parou. |
| `/fechar-sessao` | Fecha o dia: diário, um briefing por sessão, as **dores que você falou** num arquivo só, tarefas abertas pro que ficou pendente. Só commita se você mandar e nunca dá push. |
| `/task-observer` | Olha como você trabalha e **só propõe** melhorias: uma skill que faltou, um passo repetido três vezes, uma correção que você fez duas. Quem decide é você. |
| `/claude-corner` | Quando você avisa que vai sair, o Claude usa o tempo pra reler suas notas, achar conexões reais e testar ideias num lugar descartável. **Só propõe**, num arquivo. |
| `/adaptar-skill` | Te guia a fazer uma skill **sua** a partir de uma ficha em `vault/fichas-de-skills/`. Uma pergunta por vez; o Claude nunca escreve a skill por você, e "não serve pra mim" é resposta válida que fica registrada. |

As fichas de `artigo`, `conselho`, `ideia-de-produto` e `consultar-notas` já estão em
`vault/fichas-de-skills/`: elas ensinam o método, e você decide se quer uma versão sua.

## Como ela melhora com você

Três ciclos, e nos três a decisão é sua:

1. **Dores.** No fim da sessão, o que você disse que doeu fica salvo, com data, em `vault/memoria/ideias/_dores.md`.
2. **Propostas.** `task-observer` e `claude-corner` escrevem sugestões em arquivos. Nada muda pelas suas costas.
3. **Suas próprias skills.** As fichas mostram como uma skill é feita e o `adaptar-skill` te leva a fazer a sua. Você não recebe uma pronta.

Uma regra atravessa tudo: **o Claude não escreve sobre você o que você não disse.** Ele propõe; uma
linha só entra no seu perfil com o seu "sim", com a data e a sua frase literal.

## Instalação

Você precisa de `git`, Python 3.10 ou mais novo, Obsidian e Claude Code. Funciona em macOS e Linux; no
Windows não foi testado.

```sh
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
sh instalar.sh      # liga o hook de pre-commit e prova que ele funciona
claude              # rode o Claude Code na RAIZ do repo
```

`git clone`, não o zip: o hook depende do git. Se `instalar.sh` terminar com `OK — hook ativo`, está pronto.

## O primeiro dia

1. No Claude Code, digite `/conhecer` e responda. Pode responder curto ou dizer "prefiro não dizer".
2. Abra a pasta `vault/` como cofre no Obsidian.
3. Crie o seu primeiro projeto: copie `vault/projetos/exemplo-meu-primeiro-projeto/` pra `vault/projetos/<nome>/`, edite o cabeçalho e acrescente uma linha em `vault/projetos/_index.md`. Depois rode `python3 ferramentas/hub.py` pra a raiz do projeto listar os arquivos dele.
4. Escreva uma nota ligada ao projeto (o modelo está em `vault/CLAUDE.md`, seção *Primeira nota*) e tente commitar.
5. `/abrir-sessao <nome>` no começo, `/fechar-sessao` no fim.

## O que a mantém saudável

A base debaixo da bancada. É pequena de propósito e roda só com a biblioteca padrão do Python.

- **Portão das órfãs.** O hook de pre-commit bloqueia nota que não liga a nada e que nada liga a ela. O `inbox/` é isento: se a captura rápida é barrada, a pessoa desinstala. Só a nota **deste** commit é barrada; as outras viram aviso.
- **Portão dos links** (`nucleo/portao.py`). Link morto, link partido, caminho que só casa pelo nome do arquivo, `area:` inválida e arquivo ilegível (que sai como "não deu pra ler", nunca como OK).
- **Varredor de vazamento** (`nucleo/vazamento.py`). Bloqueia caminho de máquina, e-mail, telefone, CPF e uma **lista privada de termos que mora fora do repo**. Sem essa lista ele diz `NAO_VERIFICADO`, nunca "limpo".
- **CI** (`.github/workflows/prova.yml`). Instala de um clone limpo, roda os testes e a mutação, e tenta o portão das órfãs de ponta a ponta.

O hook se contorna de propósito com `git commit --no-verify`. Cada regra daqui nasceu de uma falha
real e datada, e cada uma tem um teste que falha sem ela: veja o [POR-QUE.md](POR-QUE.md).

### O hook bloqueou meu commit. E agora?

Ele diz o arquivo e o motivo. Nota órfã: ligue a nota a outra que **existe**, com um `[[wikilink]]` no
meio do texto. Vazamento: ele diz `arquivo:linha:tipo` (nunca o dado); tire o dado do arquivo. Captura
rápida? Jogue em `vault/inbox/`.

## Pra quem vai testar

Se você recebeu isto pra testar, faça nesta ordem e anote **onde travou**, o que não entendeu e o que
esperava que acontecesse:

1. Clonar e rodar `sh instalar.sh`. Deu `OK`?
2. Criar uma nota em `vault/notas/aprendizado/` sem nenhum link e tentar commitar. Bloqueou? A mensagem te ajudou a consertar?
3. `/conhecer`. As perguntas fizeram sentido? Alguma te incomodou?
4. Criar um projeto e uma nota ligada a ele. Você soube o que fazer só com o `vault/CLAUDE.md`?
5. `/fechar-sessao` no fim. O que ele colheu estava certo?
6. Tentar `/adaptar-skill` numa ficha. Você conseguiu chegar numa skill sua sem o Claude escrever por você?

Mande o que achou do jeito que for mais fácil: uma mensagem pra quem te passou, ou uma issue no repo.

## O que está verificado, e o que não está

- Testes: `python3 -m pytest -q` deu **186 passaram, 2 pulados** em 03/10.
- Mutação: `python3 tests/mutar.py` quebra cada check, um de cada vez, e deu **102 de 102 mutantes mortos, 0 vivos** em 03/10.
- CI: **8 de 8 jobs verdes** em 03/10 (commit `0e5b8d2`), em ubuntu e macOS com Python 3.10, 3.11, 3.12 e 3.13. Cada job parte de um checkout limpo, roda o `instalar.sh`, os testes, a mutação e a varredura de vazamento, e prova o portão das órfãs de ponta a ponta.
- Dois testes comparam este portão com o vault privado do autor, que não está neste repo. Eles são **pulados** (saem como pulados, não como passados).
- **Ninguém além do autor usou ainda.**

## Próximos passos

`artigo`, `conselho`, `ideia-de-produto` e `consultar-notas` como skills de verdade (as fichas já existem); um comando pra listar tarefas; uma skill que transforma uma falha sua em regra mais teste.

## Licença

MIT. Veja [LICENSE](LICENSE).
