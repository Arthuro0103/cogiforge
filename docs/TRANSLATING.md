# Translating cogiforge back to Portuguese

cogiforge was written in Portuguese first and moved to English in October 2026. If you want to use it
in Portuguese (or any other language), this page tells you what to change, what to leave alone, and how to
check that nothing was missed.

**You do not need to translate anything to *use* it in Portuguese.** The skills tell Claude to talk to you
and write your notes in the language you write in. This page is for people who want the files themselves in
another language.

## Three kinds of text

| Kind | Examples | Safe to translate? |
|---|---|---|
| **Prose** | the skills, `README.md`, `TUTORIAL.md`, `WHY.md`, the worksheets, the example notes | Yes. Nothing reads it except you and Claude. |
| **Names the code reads** | folder names, `area:` and `target:` in the frontmatter, the check names, the JSON keys, the tokens a script prints | **Only together with the code and the tests.** One table below lists them all. |
| **Names other tools read** | `tags: task`, `status: open`, `in-progress`, `done`, `priority` (TaskNotes) | **No.** Leave them in English. |

## The table of names the code reads

The first column is what this repo uses. The second is what it used before. The test
`tests/test_equivalence.py` reads this table to turn the demo notes back into Portuguese and compare the gate
here with the author's private one, so **keep the markers and the three-column format**.

<!-- names:start -->
| en | pt | kind |
|---|---|---|
| notes | notas | folder |
| tasks | tarefas | folder |
| projects | projetos | folder |
| memory | memoria | folder |
| instructions | instrucoes | file |
| home | _indice | file |
| learning | aprendizado | area |
| technology | tecnologia | area |
| life | vida | area |
| target | alvo | key |
| none | nenhum | value |
| dead-link | link-morto | check |
| broken-link | link-partido | check |
| dead-target | alvo-morto | check |
| orphan | orfa | fixture |
| wrong-area | area-errada | fixture |
| broken-frontmatter | frontmatter-quebrado | fixture |
| leaked | vazou | fixture |
| loose-capture | captura-solta | fixture |
| control-a | controle-a | fixture |
| control-b | controle-b | fixture |
| control-c | controle-c | fixture |
| control-d | controle-d | fixture |
| control-e | controle-e | fixture |
| control-relative-link | controle-link-relativo | fixture |
<!-- names:end -->

## Everything else that changed names

| en | pt | where |
|---|---|---|
| `core/` | `nucleo/` | folder with the three checkers |
| `tools/` | `ferramentas/` | folder with `hub.py` |
| `gate.py` | `portao.py` | link and frontmatter check |
| `ring.py` | `anel.py` | orphan check |
| `leak.py` | `vazamento.py` | personal-data scanner |
| `install.sh` | `instalar.sh` | installer |
| `blocklist.txt` | `negra.txt` | private word list in `~/.config/cogiforge/` (the old name is still read, with a warning) |
| `.leakignore` | `.vazamentoignore` | planted fixtures the scanner skips |
| `tests/mutate.py`, `tests/counts.py` | `tests/mutar.py`, `tests/contagem.py` | |
| `--no-ignore`, `--require-list`, `--audit` | `--sem-ignorar`, `--exigir-lista`, `--auditar` | flags |
| `NOT_VERIFIED`, `UNREADABLE`, `WARNING`, `FAILS`, `COMMIT BLOCKED`, `How to fix` | `NAO_VERIFICADO`, `ILEGIVEL`, `AVISO`, `REPROVA`, `COMMIT BLOQUEADO`, `Como consertar` | what the scripts print and the hook greps |
| `<!-- hub:start -->`, `<!-- hub:end -->` | `<!-- hub:inicio -->`, `<!-- hub:fim -->` | the generated block in a project's `instructions.md` |
| `/onboard`, `/open-session`, `/close-session`, `/adapt-skill` | `/conhecer`, `/abrir-sessao`, `/fechar-sessao`, `/adaptar-skill` | skill folders in `.claude/skills/` |

## Glossary

| en | pt |
|---|---|
| workbench | bancada |
| worksheet | ficha |
| pain | dor |
| session / diary / briefing | sessão / diário / briefing |
| gate | portão |
| ring | anel |
| leak | vazamento |
| blocklist | lista negra |
| orphan / edge | órfã / aresta |
| target | alvo |
| quick capture | captura rápida |
| verdict | veredito |
| deliberate bypass | escape consciente |
| verbatim quote | citação literal |
| throwaway | descartável |
| proposal / Claude's guess | proposta / palpite do Claude |
| The rules / Never | A lei / Nunca |
| TRIGGERS / Do NOT trigger | GATILHOS / NÃO dispare |

## How to translate, in this order

1. Prose first: the skills, the worksheets, the docs. Keep the **fixed tokens** exactly as written.
2. Then the names. Change one row of the table at a time, **in the code, the tests, the CI and the hook
   together**, and run `python3 -m pytest -q` and `python3 tests/mutate.py --dry` after each one. `--dry`
   tells you in seconds if a mutant no longer finds its line.
3. Run the full `python3 tests/mutate.py` once at the end. Every mutant has to die.

## How to check that nothing was missed

Run these from the repo root. In the English version they print nothing, apart from the lines that are
Portuguese on purpose (the planted fixture in `demo/notes/life/leaked.md`, the old `negra.txt` fallback, and
this page).

```sh
# accented letters
git ls-files -z | xargs -0 grep -nIP '[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]'
# common Portuguese words
git ls-files -z | xargs -0 grep -nIwiE 'nao|voce|tambem|entao|isso|quando|porque|ainda|pasta|arquivo|tarefa|falha|veredito|orfa|alvo|nenhum'
# file names
git ls-files | grep -iE 'notas|tarefas|projetos|memoria|instrucoes|indice|nucleo|ferramentas|portao|anel|vazamento|instalar'
```

`tests/test_no_portuguese.py` runs the same search and keeps a list of allowed exceptions in
`tests/pt_allowlist.txt`, one `path: reason` per line.
