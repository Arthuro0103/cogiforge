# cogiforge (LEIA-ME em português)

> Este é o README em português. A versão em inglês, [README.md](README.md), é a de referência: se as duas
> discordarem, vale a inglesa. As skills e os docs do repo estão em inglês; elas mandam o Claude falar com você
> na língua em que você escreve. Para traduzir também os arquivos, veja [docs/TRANSLATING.md](docs/TRANSLATING.md).

**cogiforge é um segundo cérebro em Obsidian + Claude Code que aprende como você trabalha e não escreve nada
sobre você que você não tenha dito.** *Cogito, ergo sum*: uma bancada criativa para a cabeça. Ele guarda seu
trabalho, a escola e a vida pessoal num lugar só, **organiza seus projetos, ideias e tarefas, ajuda a escrever e
a planejar, e melhora junto com você** conforme você usa.

> **Status: alfa (v0.x).** Nasceu do cofre de trabalho do próprio autor. É novo, então espere arestas: se algo
> quebrar, abra uma issue. Passo a passo de cada parte: [TUTORIAL.md](TUTORIAL.md).

## Começo rápido

Você precisa de `git`, Python 3.10+, Obsidian e Claude Code. macOS e Linux são o que o CI prova. O Windows tem
um instalador (`install.ps1`) e um job de CI só informativo, que não garante estar verde; veja
[docs/WINDOWS.md](docs/WINDOWS.md), onde cada afirmação não confirmada está marcada `[VERIFY]`. Para rodar os
testes do próprio repo você também precisa do `pytest` (`python3 -m pip install pytest`).

```sh
git clone https://github.com/Arthuro0103/cogiforge.git
cd cogiforge
sh install.sh      # liga o hook de pre-commit e prova que ele funciona
claude              # roda o Claude Code na raiz do repo
```

Depois, dentro do Claude Code, digite `/cf-onboard`. Abra a pasta `vault/` como cofre no Obsidian. Quando tiver um
projeto, use `/cf-open-session <nome>` para começar e `/cf-close-session` para encerrar o dia. O projeto de
exemplo `vault/projects/example-my-first-project/` mostra o formato. As tarefas precisam do plugin público
TaskNotes (instale pela loja de plugins da comunidade do Obsidian); o mapa de conexões opcional precisa do
graphify. Os dois estão no [tutorial](TUTORIAL.md).

## Para quem é

| Você | Comece por aqui |
|---|---|
| **Só você** | `/cf-onboard`, depois `/cf-open-session <projeto>` e `/cf-close-session`. |
| **Estudando** | `/cf-study <tema>`: você escolhe como aprende, a lembrança vem primeiro, e "dominado" exige um reteste em outro dia. Veja [docs/STUDENTS.md](docs/STUDENTS.md). |
| **Uma equipe ou uma escola** | `sh install.sh --team <seu-handle>`, uma pasta por pessoa, papéis de admin e membro. Veja *Equipes e escolas*, [docs/SYNC.md](docs/SYNC.md) e [docs/WINDOWS.md](docs/WINDOWS.md). |

## Por que existe

O cogiforge saiu de usar o Claude num cofre de verdade. Três decisões o moldaram:

1. **O Claude não decide quem você é.** Nada sobre você é escrito se você não disse. Uma linha só entra no seu perfil com o seu "sim", a data e a sua citação literal.
2. **Uma regra só fica se uma falha real a justifica.** Toda regra deste repo vem de um erro com data e tem um teste que fica vermelho sem ela. Exemplos do [WHY.md](WHY.md): um verificador de links que dizia OK com 58 links quebrados, uma checagem que não tocou em nada e mesmo assim disse OK, um portão burlado com `--no-verify` três vezes e depois seis.
3. **Ele propõe, você decide.** As skills escrevem sugestões em arquivos. Nada muda pelas suas costas.

## O que você recebe

| Peça | O que faz |
|---|---|
| `vault/` | A bancada: `inbox/` para captura rápida, `notes/` para notas processadas, `projects/` com um arquivo-raiz por projeto, `memory/` para o que *você* disse, `tasks/` para tarefas. Abra esta pasta no Obsidian. |
| `/cf-onboard` | Apresentação. Faz uma pergunta de cada vez, cada uma seguindo a sua última resposta, e escreve o que **você disse**, com data e entre aspas. Nunca adivinha. |
| `/cf-open-session <projeto>` | Começa o trabalho num projeto: lê a raiz, as últimas entradas do diário e as tarefas abertas, e diz onde você parou. |
| `/cf-close-session` | Encerra o dia: diário, um resumo por sessão, as **dores que você falou** juntas num arquivo, tarefas abertas para o que ficou pendente. Só faz commit se você mandar e nunca dá push. |
| `/cf-ask` | Responde só a partir das suas notas, com citações que o `tools/ask.py cite` consegue conferir. |
| `/cf-task-observer` | Observa como você trabalha e **só propõe** melhorias (uma skill que falta, um passo repetido três vezes, uma correção feita duas vezes). Você decide. |
| `/cf-claude-corner` | Quando você diz que vai sair, o Claude usa o tempo para reler suas notas, achar conexões reais e testar ideias num lugar descartável. **Só propõe**, num arquivo. |
| `/cf-new-project <nome>` | Cria um projeto: pergunta o nome, depois o que existe no mundo quando der certo (a sua frase, copiada palavra por palavra), mostra um ensaio e só cria depois do seu "sim". |
| `/cf-new-rule` | Transforma um erro real seu numa regra que dá para checar: o erro primeiro (o que houve, quando, o número), depois um par de entradas, um teste que você vê vermelho, a regra, uma mutação e uma entrada no `WHY.md`. Sem erro datado não há regra; nada fora de `vault/` é escrito sem o seu "sim". |
| `/cf-whats-real` | Guarda, por projeto, o que **funciona (com prova)**, o que é **simulado ou demo** e o que é **desconhecido**. Um item só vai para "funciona" com prova rodada de novo. |
| `/cf-know-my-product` | Entrevista você sobre o seu produto e junta as suas dores com as palavras literais e a data. Você aprova antes de salvar. |
| `/cf-brainstorm` | Brainstorming para qualquer produto, projeto, estudo ou ideia solta. Confere o que o cofre já diz, propõe **três caminhos realmente diferentes**, recomenda um **sem escolher por você** e para num resumo que você aprova. |
| `/cf-extract-routine` | Tira uma rotina real da sua cabeça por entrevista. O que você não sabe fica `[CONFIRM]`; o Claude nunca inventa um passo. |
| `/cf-import-knowledge` | Traz uma base existente (outro cofre, pasta, documentos, exportações de chat) para o inbox e guia a triagem, alvo primeiro. |
| `/cf-adopt` | Adota um cofre que você já tem, no lugar, sem copiar nada. |
| `/cf-brand <modo>` | Guarda a sua marca nas suas palavras: regras de voz, DNA, mensagem e design system de um projeto, sem cores padrão. Veja [docs/BRAND.md](docs/BRAND.md). |
| `/cf-study <tema>` | Ajuda a aprender do jeito que você quer; "dominado" exige reteste em outro dia. |
| `/cf-adapt-skill` | Ajuda você a escrever a **sua própria** skill a partir de uma ficha em `vault/skill-worksheets/`. O Claude nunca a escreve por você. |

As tarefas são notas em `vault/tasks/`, gerenciadas pelo plugin público [TaskNotes](https://github.com/callumalpass/tasknotes) do Obsidian (MIT). O mapa de conexões opcional usa o [graphify](https://github.com/Graphify-Labs/graphify) (Apache-2.0), que você instala por conta própria.

## Como ele melhora com você

Três ciclos, e em todos a decisão fica com você:

1. **Dores.** No fim da sessão, as suas palavras sobre o que doeu são salvas, com data, em `vault/memory/ideas/_pains.md`.
2. **Propostas.** `cf-task-observer` e `cf-claude-corner` escrevem sugestões em arquivos. Nada é mudado pelas suas costas.
3. **Suas próprias skills.** As fichas ensinam como uma skill é feita, e `cf-adapt-skill` guia você a fazer a sua. Ninguém entrega uma pronta.

Uma regra dura atravessa tudo: **o Claude não escreve nada sobre você que você não tenha dito.** Ele propõe; uma
linha só entra no seu perfil com o seu "sim", a data e a sua citação literal.

## Equipes e escolas

Um cofre para um grupo, uma pasta por pessoa: `vault/people/<handle>/` (memória, inbox, diário). Ligue com
`sh install.sh --team <seu-handle>`: ele escreve `vault/roles.txt` com você como admin (o seu `git config user.email`)
e copia `vault/people/_template/`. Sem o `roles.txt` nada muda: o modo solo é idêntico.

- **admin** passa em tudo. **membro** trabalha na própria pasta, em `notes/` e em projetos existentes; o hook de pre-commit bloqueia um membro que mexa na pasta de outra pessoa, em `roles.txt`, em `areas.txt` ou crie um projeto.
- **O limite honesto:** o git não tem permissão por pasta. Os papéis são uma convenção mais um hook local, e `git commit --no-verify` o pula. A garantia de verdade é o servidor: use um `CODEOWNERS` e proteção de branch com revisão obrigatória.
- **Quem clona lê tudo.** O que é íntimo vai em `vault/people/<handle>/private/`, que está no gitignore e nunca sai da sua máquina.

## Guias

Os guias estão em inglês. Cada um diz, em uma linha, para que serve:

- [AGENTS.md](AGENTS.md): as regras de operação numa forma que qualquer agente de código lê.
- [docs/EXPORTING-CHATS.md](docs/EXPORTING-CHATS.md): exportar seu histórico de chat e trazê-lo para o cofre.
- [docs/RESEARCH.md](docs/RESEARCH.md): pesquisar com o cofre, primeiro as suas notas, depois a internet, com toda afirmação de fora marcada até ser conferida.
- [docs/PRIVATE.md](docs/PRIVATE.md): pedir ao Claude Code que não leia algumas pastas, e o limite disso.
- [docs/WINDOWS.md](docs/WINDOWS.md): o caminho nativo em PowerShell e o caminho em WSL, com o que está e o que não está verificado.
- [docs/USING-OTHER-MODELS.md](docs/USING-OTHER-MODELS.md): usar o cofre com outros agentes, e o que se perde sem as skills do Claude Code.
- [docs/SYNC.md](docs/SYNC.md): manter o cofre sincronizado sem duplicatas nem conflitos.
- [docs/STUDENTS.md](docs/STUDENTS.md): estudar o que você quer, do jeito que você quer.
- [docs/CONTEXT.md](docs/CONTEXT.md), [docs/PRODUCT-AND-PAINS.md](docs/PRODUCT-AND-PAINS.md) e [docs/BRAND.md](docs/BRAND.md): contexto, produto e dores, marca.

## O que o mantém saudável

Esta é a base sob a bancada. É pequena de propósito e roda só com a biblioteca padrão do Python.

- **Portão de órfãs.** O hook de pre-commit bloqueia uma nota que não liga a nada e a que nada liga. O `inbox/` é isento: se a captura rápida for bloqueada, as pessoas desinstalam a coisa. Rígido demais? Ponha `orphan: warn` em `vault/gate.txt`.
- **Checagem de links** (`core/gate.py`). Links mortos, links quebrados, um caminho que só casa pelo nome do arquivo, um `area:` inválido, arquivos ilegíveis (relatados como "não deu para ler", nunca como OK).
- **Detector de vazamento** (`core/leak.py`). Bloqueia caminhos de máquina, e-mails, telefones, CPF e uma **lista privada de termos que mora fora do repo**. Sem essa lista ele diz `NOT_VERIFIED`, nunca "limpo".
- **Nada em português por acidente** (`tests/test_no_portuguese.py`). O repo migrou para o inglês em outubro de 2026; as exceções deliberadas, como este arquivo, estão em `tests/pt_allowlist.txt`, uma por linha, com o motivo.
- **CI** (`.github/workflows/prova.yml`). Instala de um clone limpo, roda os testes e a checagem de mutação, e experimenta o portão de órfãs de ponta a ponta.

O hook pode ser burlado de propósito com `git commit --no-verify`. Toda regra daqui vem de uma falha real e
datada, e cada uma tem um teste que falha sem ela: veja o [WHY.md](WHY.md).

## O que está verificado, e o que não está

As medições com número, comando e commit estão no [README.md](README.md), seção *What is verified, and what is
not*. Não copiei os números para cá de propósito: uma cópia envelhece sozinha. Em resumo: macOS e Linux são provados
pelo CI; o Windows **não** é declarado como suportado; dois testes que comparam o verificador de links com o cofre
privado do autor ficam **pulados**. **É novo.** Se algo quebrar ou você travar, diga onde: é o que há de mais útil
que você pode mandar.

## Trazendo uma base de conhecimento existente

Uma equipe, uma escola ou uma pessoa geralmente já começa com notas. A importação é uma cópia mais uma conversão:
os seus originais nunca são tocados e nada some em silêncio.

```sh
python3 tools/import.py ~/minha-wiki --dry-run          # plano: imprime o relatório, não escreve nada
python3 tools/import.py ~/minha-wiki [--person HANDLE]  # para vault/inbox/imported/minha-wiki
```

Ele escreve um `_import-report.md` ao lado da cópia: todo arquivo da origem aparece como convertido, copiado,
inalterado, ignorado ou não convertido, com o motivo, e a conta tem de fechar. Depois roda o detector de
vazamento e lista `arquivo:linha:tipo` (nunca o dado); um vazamento não impede a cópia, mas o commit fica
bloqueado até limpar. Formatos: `.md`, `.txt`, `.html`, `.csv`, `.json` e imagens são diretos; `.pdf`, `.docx`,
`.pptx` e `.xlsx` precisam do [docling](https://github.com/docling-project/docling); o resto vai para
`_unconverted/` e é listado, nunca descartado.

## Adotando um cofre que você já tem

Se as suas notas já moram num cofre do Obsidian, não precisa começar do zero nem copiar nada. `tools/adopt.py`
trabalha no lugar:

```sh
python3 tools/adopt.py ~/meu-cofre                  # ensaio (o padrão): imprime o plano, não escreve nada
python3 tools/adopt.py ~/meu-cofre --apply --yes    # escreve só o que o plano listou
```

O plano lista as áreas que ele deduz das suas pastas, o que instalaria (um hook de pre-commit e uma pequena
configuração) e a **dívida que você tem hoje**, salva em `.cogiforge/baseline.json`. O hook só julga as notas de
cada commit, então a dívida antiga não bloqueia nada: ele só impede que problemas novos entrem. Um arquivo que já
existe nunca é sobrescrito, nenhuma nota é tocada e a ferramenta nunca roda `git init` por você. A skill
`cf-adopt` guia o processo.

## Licença

MIT. Veja [LICENSE](LICENSE).
