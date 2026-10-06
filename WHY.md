# POR-QUE

Cada regra deste repo nasceu de um erro real, com data. O erro está contado sem nomes de projeto, e o
**teste que o pega mora aqui**: dá pra rodar e ver vermelho sem a regra, verde com ela.

Isto não é o que a bancada faz (isso está no [LEIA-ME](LEIA-ME.md)). É a base debaixo dela: o que
impede a bancada de apodrecer sem ninguém perceber.

## Como uma regra entra

1. **Um erro com data e número**, do tipo que já aconteceu, não do tipo que podia acontecer.
2. **Um teste em par**: a entrada que sabidamente falha **e** uma plausível que tem que passar.
3. **Uma mutação**: `tests/mutar.py` quebra cada check de propósito e exige que a suíte fique vermelha. Teste que continua verde com o check quebrado não testa nada.

Regra sem erro que a justifique, ou sem teste que falhe sem ela, não entra. Quando você achar um erro
seu, registre aqui com a data, escreva o teste que falha, e só então escreva a regra. (A skill que
automatiza isso, `regra-nova`, ainda não existe.)

## Os erros

### 1. O link com caminho velho que o verificador aprovava (25/08)

**O que quebrou.** Um conjunto de notas foi movido de pasta. 58 wikilinks em 38 arquivos continuaram
apontando pro caminho antigo. O verificador dizia "tudo certo" porque, quando o caminho não existia,
ele caía pro **nome do arquivo** e achava a nota. O Obsidian não faz isso quando o link traz
caminho: os 58 estavam quebrados na tela, com o verificador dizendo que estava tudo bem.

**A regra.** Link **com** caminho só vale pelo caminho. Só o link **sem** barra resolve por nome.

**Quem pega.** `nucleo/portao.py`, check `link-morto`.
**O teste.** `tests/test_portao.py::test_link_morto_reprova` (o caso `[[outra/pasta/b]]`, onde `b`
existe em outra pasta) e `test_alvo_so_casa_por_basename_com_caminho_declarado_reprova`.

### 2. Sete dos oito checks podiam ser apagados e o teste continuava verde (05/09)

**O que quebrou.** Alguém quebrou de propósito um check de cada vez pra ver se a suíte percebia.
A suíte da época só tinha teste pra 1 dos 8 checks: os outros 7 podiam ser apagados e nada ficava
vermelho.

**A regra.** Todo check tem que ter um teste que falha quando ele é quebrado.

**Quem pega.** `tests/mutar.py`, que roda no CI como portão: mutante vivo reprova.
**O teste.** O próprio `mutar.py`. Resultado hoje: **105 de 105 mutantes mortos, 0 vivos** (03/10).

### 3. Um verificador que não tocou em nada e disse OK (11/09)

**O que quebrou.** Um check de deploy imprimiu "9 · 0 falharam" **sem nunca falar com o servidor**.
Zero falhas, porque nada foi tentado.

**A regra.** Um check que não tocou em nada **não pode dizer OK**. Ele diz `NAO_VERIFICADO`.

**Quem pega.** `nucleo/vazamento.py`: sem a lista privada de termos, ele roda só os padrões
genéricos e diz `NAO_VERIFICADO`; `--exigir-lista` vira rc 3.
**O teste.** `tests/test_hook_e2e.py::test_sem_lista_privada_avisa_nao_verificado_e_nao_bloqueia`.

### 4. 389 notas órfãs viraram 1, e cinco novas nasceram na mesma sessão (13 e 14/09)

**O que quebrou.** Uma sessão costurou 254 links **à mão** e levou as órfãs de 389 pra 1. Na mesma
sessão nasceram 5 órfãs novas. Consertar o acervo não fecha a torneira. O hook que fecha só foi
escrito no dia seguinte.

**A regra.** Nota sem nenhum link de entrada ou de saída é barrada **no commit**, não depois.

**Quem pega.** `nucleo/anel.py` pelo hook `.githooks/pre-commit`.
**Os testes.** `tests/test_anel.py::test_gate_reprova_orfa_e_ensina_o_conserto` e
`tests/test_hook_e2e.py::test_orfa_bloqueia_o_commit_e_ensina`.

### 5. O hook que existia no disco e nunca rodava (14/09)

**O que quebrou.** `core.hooksPath` é configuração **local** do git. Num clone novo o hook vem no
disco e **não dispara**: a proteção existe e não protege.

**A regra.** A instalação ativa o hook e **prova** que ele está ativo; um teste reprova quando não está.

**Quem pega.** `instalar.sh` (falha alto, rc ≠ 0) e `tests/test_hook_ativo.py`. O CI ainda confere que
o clone **começa sem** `hooksPath` e que passa a tê-lo depois do `instalar.sh`.
**Os testes.** `tests/test_hook_ativo.py::test_hookspath_aponta_pro_githooks` e
`tests/test_hook_e2e.py::test_sem_hookspath_o_hook_nao_dispara`.

### 6. Verificador que não conseguiu ler o arquivo e chamou de dívida (13 e 14/09)

**O que quebrou.** Um arquivo sem permissão de leitura saía como "erro de YAML" e entrava na conta como
dívida de formatação. "Não consegui ler" e "li e está errado" são coisas diferentes.

**A regra.** Arquivo ilegível tem veredito próprio: rc 3, `ILEGIVEL`, nunca limpo.

**Quem pega.** `nucleo/portao.py`.
**Os testes.** `tests/test_portao.py::test_cli_arquivo_ilegivel_sai_3_nunca_limpo` e
`test_ilegivel_e_arquivo_nao_utf8_nunca_e_limpo`.

### 7. O verificador que dava OK ao que não conferiu, de novo (05/09, e hoje)

**O que quebrou, no original.** 3 dos 8 checks abortavam na primeira linha fora da pasta de notas.
Rodar o portão num rascunho que ainda não estava lá conferia só 5 dos 8, **em silêncio**.

**E o mesmo erro apareceu aqui, hoje (03/10).** Ao escrever este arquivo, testei o portão num rascunho
**fora** do vault. Com um vault de caminho absoluto ele saiu **limpo (rc 0)** sem ter conferido nada;
com um vault relativo, derrubou com traceback. O teste foi escrito antes do conserto, falhou, e só
então o portão foi consertado.

**A regra.** O portão só confere o que está **dentro** do vault; arquivo de fora sai com rc 2 e uma
mensagem, nunca como OK.

**Quem pega.** `nucleo/portao.py`.
**O teste.** `tests/test_portao.py::test_arquivo_fora_do_vault_sai_2_nunca_limpo_e_sem_traceback`.
Há também um mutante dedicado em `tests/mutar.py`.

### 8. O gate que barra o que você não fez vira o gate que você pula (20 e 24/09)

**O que quebrou.** Um gate que reprovava o commit por causa de uma nota que **não era sua**, ou de um
rascunho que nem estava no commit, foi contornado: 3 commits, depois 6, com `--no-verify`.

**A regra.** O hook só olha o que **este** commit leva. O resto vira aviso. E a captura rápida
(`inbox/`) nunca é barrada.

**Quem pega.** `nucleo/anel.py --gate --stage`.
**Os testes.** `tests/test_hook_e2e.py::test_orfa_de_fora_do_commit_so_avisa`, `test_inbox_nunca_e_barrado`
e `test_no_verify_e_o_escape_consciente`.

### 9. O `;` no laço que deixou o commit passar (25/09)

**O que quebrou.** Um laço de shell rodava o verificador e o `git commit` separados por `;`. Dois
commits saíram com o verificador reprovando, porque o commit rodava mesmo assim.

**A regra.** O bloqueio mora **no hook do git**, que todo `git commit` atravessa, e não na disciplina
de quem escreve o laço.

**Quem pega.** `.githooks/pre-commit`.
**O teste.** `tests/test_hook_e2e.py::test_orfa_bloqueia_o_commit_e_ensina` (o commit sai com erro e o
HEAD não anda). O CI repete isso num clone limpo.

### 10. O plugin que escreve o que o verificador não entende, e a tarefa que nasce sem link (03/10)

**O que quebrou.** Ao integrar o plugin de tarefas, medimos duas tarefas no formato dele. Uma igual ao
exemplo da documentação passou. A outra, com **tempo registrado** (`timeEntries`, uma lista de mapas: YAML
válido), **reprovou no portão** como "yaml fora do subconjunto". E uma tarefa **sem projeto**, do tipo que a
interface cria sem pedir link, era **órfã**: o hook barraria o commit. **Ressalva:** o formato dessas duas
foi montado a partir da documentação do plugin, não de uma saída real dele (o Obsidian não foi rodado aqui).

**A regra.** O que o plugin escreve em `tasks/` é do plugin: o portão não julga o YAML dali e a pasta é
isenta de órfã (como o `inbox/`). Link morto dentro da tarefa continua reprovando.

**Quem pega.** `nucleo/portao.py` (pasta `tasks/`) e `nucleo/anel.py` (`DEPOSITOS`).
**Os testes.** `tests/test_portao.py::test_frontmatter_de_tarefa_do_plugin_nao_e_julgado_pelo_subconjunto`,
`test_o_mesmo_yaml_fora_de_tarefas_continua_reprovando` e `test_link_morto_dentro_da_tarefa_ainda_reprova`;
`tests/test_anel.py::test_tarefa_do_plugin_sem_projeto_e_isenta_mas_liga_o_que_aponta` e
`test_so_tarefas_na_raiz_e_isenta_nao_um_nome_parecido`. Há três mutantes dedicados em `tests/mutar.py`.
Os testes foram escritos antes do conserto e falharam.

## O que ainda não está coberto

### Uma regex que cortava a extensão e fabricou 18 caminhos "mortos" (06/09)

O verificador do autor tinha um check que conferia caminhos citados no texto, e a regex lia `.tsx`
como `.ts`: 18 caminhos "mortos" eram esse corte. **Este template não tem esse check** (são cinco
checks, e nenhum confere caminho em texto corrido), então não existe regra nem teste aqui. Fica
registrado pra não parecer que foi esquecido: quando o check for portado, ele entra com o teste.
