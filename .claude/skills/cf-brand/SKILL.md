---
name: cf-brand
description: Interviews the user, one question at a time, and writes the brand pieces of a person or a project using only their own words - voice rules for the person (vault/memory/voice.md) or for one project (inherits the person's and keeps only what differs), and for a project the DNA, the messaging, the design system (design.md plus tokens.json, with no default color) and a manual that assembles them. Verbatim quotes, nothing deduced, a "yes" before anything is saved. Checks texts and previews tokens with two offline tools. TRIGGERS - "/cf-brand voice --person", "/cf-brand voice --project <name>", "/cf-brand dna <name>", "/cf-brand messaging <name>", "/cf-brand design <name>", "/cf-brand manual <name>", "my voice rules", "brand of my project", "design system", "brand manual". Do NOT trigger to get to know the user themselves (that is cf-onboard), to write the product brief (cf-know-my-product), to create a project (cf-new-project), nor to choose between two paths (that is a decision, not an interview).
---

# cf-brand: the brand comes from what the person said, not from the model

## Why it exists

A brand written by the model is a guess with good typography: a tone nobody uses, values nobody chose, a
palette picked because it looked fine. Later sessions read that guess back as fact and write in a voice that
is not the person's. The fix is the same one `cf-onboard` and `cf-know-my-product` use: an interview, one
question at a time, and the file keeps the person's words. This skill organizes what the person said into
pieces that other sessions and two small tools can check. It does **not** create an identity on its own. The
guide for people is `docs/BRAND.md`.

## The rules

1. **One question per message.** Never a list. The next question depends on the answer.
2. **Context before options.** One sentence on why you ask, then 2 to 4 concrete options
   (`AskUserQuestion`), always with room for a free answer.
3. **A short answer is an answer.** "I don't know yet" is valid: write it as that. Do not insist or rephrase.
4. **Nothing deduced.** If you inferred something, ask. A field with no answer stays empty.
5. **Verbatim only for what they typed.** A quote keeps their exact words, with the date. If they clicked an
   option you wrote, record "chose option X", with no quotation marks.
6. **Never write without the "yes".** Show the whole file as a draft in the chat, ask *"can I save it like
   this? (yes/no)"*, and save only after the yes. **STOP and wait.**
7. **No project name, no project mode.** Ask which project (list `vault/projects/`). Never guess.
8. **The template carries nothing of anyone.** No default color, font, tone or value. Every token in
   `tokens.json` comes from the user, typed or chosen by them.
9. **No real names of third parties** in what you write. Use roles or handles.
10. **Never say "OK" without a check that touched something.** `voice_check.py` returning rc 3 means
    `NOT_VERIFIED` (there were no rules to check against), not clean.

> Talk to the user in the language the user writes in. Never translate a quote: verbatim quotes stay in the
> original language. Fixed tokens (frontmatter keys, section names, paths, JSON keys) stay as written.

## The modes

| mode | asks | writes | model |
|---|---|---|---|
| `/cf-brand voice --person` | how the person writes when they are being themselves | `vault/memory/voice.md` (team mode: `vault/people/<handle>/memory/voice.md`) | [[skill-worksheets/brand-voice\|brand-voice]] |
| `/cf-brand voice --project <name>` | only where this project's voice differs from the person's | `vault/projects/<name>/brand/voice.md`, with `inherits:` | [[skill-worksheets/brand-voice\|brand-voice]] |
| `/cf-brand dna <name>` | why it exists and for whom | `vault/projects/<name>/brand/dna.md` | [[skill-worksheets/brand-dna\|brand-dna]] |
| `/cf-brand messaging <name>` | what it is, in one sentence | `vault/projects/<name>/brand/messaging.md` | [[skill-worksheets/brand-messaging\|brand-messaging]] |
| `/cf-brand design <name>` | how it should look | `vault/projects/<name>/brand/design.md` and `tokens.json` | [[skill-worksheets/brand-design\|brand-design]] |
| `/cf-brand manual <name>` | **asks no interview question** | `vault/projects/<name>/brand/manual.md` | none: it assembles the four above |

Modes run one at a time. Running one does not require the others: a project can have messaging and no design.

## The steps

### 0. Before any mode (you, Claude)

Team mode: if `vault/roles.txt` exists, find who is talking the way `cf-onboard` does (`git config user.email`
matched against `vault/roles.txt`), and use `vault/people/<handle>/memory/` wherever this skill says
`vault/memory/`. Never open another person's folder.

```bash
ls vault/projects/
cat vault/memory/voice.md 2>/dev/null
ls vault/projects/<name>/brand/ 2>/dev/null
cat vault/projects/<name>/product.md 2>/dev/null
```

If the file of this mode already has answers, this is a review: say what it holds and ask what changed.

### 1. `voice --person`

Writes `vault/memory/voice.md` (team mode: the path from step 0). The file has exactly these sections, in this order, and the tools read them by name:

```
---
type: voice
scope: person
---

## Phrases
- YYYY-MM-DD | "literal quote"

## Never say
- term

## Avoid
- term

## Pairs
- say: "..." | not: "..."
```

Interview, one question per message:

| section | possible opening |
|---|---|
| `## Phrases` | "Paste or type a sentence you wrote recently that sounds like you." Each answer is one line, with today's date and their words in quotes. |
| `## Never say` | "Is there a word or expression you would never put your name under?" One term per line. |
| `## Avoid` | "Is there a word you use but would rather use less?" One term per line. |
| `## Pairs` | "Give me one way you would say something, and the way you would not." Both halves are theirs. |

Never fill a section with a term you think they would dislike. A section with no answer stays empty under
its heading. Show the draft, ask for the yes, save.

### 2. `voice --project <name>`

Read the person's `voice.md` first. If it does not exist, say so and offer `/cf-brand voice --person` before
this one; do not invent a base. The project file has the same four sections and the frontmatter
`type: voice`, `scope: project`, `inherits: vault/memory/voice.md` (or the team path). Ask only **what
differs** in this project ("Is there anything you say here that you would not say elsewhere?"). Never copy the
person's lines into the project file: what is inherited stays in the person's file. Draft, yes, save.

### 3. `dna <name>`

Read `product.md` and do not ask again what it already answers; link it instead. Fields, from
[[skill-worksheets/brand-dna|brand-dna]]: purpose, audience, what it is NOT, values, promise. Possible
openings: "Why does this exist, in your words?", "Who is it for? A role is fine.", "Name one thing people
might expect from it that it will never be." Each answer is a quote with the date. Draft, yes, save.

### 4. `messaging <name>`

Fields, from [[skill-worksheets/brand-messaging|brand-messaging]]: the one-liner ("In one sentence, what is
it?"), the 30-second pitch, and a short bio for each platform the user names. Ask which platforms; never
assume a list. If they ask you to shorten their sentence, show your version next to theirs and keep theirs
unless they say yes to yours. Draft, yes, save.

### 5. `design <name>`

Fields, from [[skill-worksheets/brand-design|brand-design]]: colors (a token name, a hex value, what it is
used for), type (heading and body), spacing scale, corner radius, three components in their own description,
and the text/background pairs to check. Possible opening: "How should this look? Describe it, or name
something it should look like."

- A color described in words ("a dark blue") is recorded in `design.md` in their words. It enters
  `tokens.json` only when they type a hex or **choose** one from 2 to 4 candidates you show; record
  "chose option X". Never pick it for them.
- `tokens.json` follows this contract, and a field with no answer is left out, never filled with a default:

```json
{
  "name": "<project name>",
  "colors": {"<token>": "#rrggbb"},
  "type": {"heading": "<font>", "body": "<font>"},
  "space": [4, 8, 16],
  "radius": 4,
  "pairs": [["<fg-token>", "<bg-token>"]]
}
```

  The numbers above show the shape only; the user's numbers replace them.

Show both drafts and ask for the yes. After saving, run the preview and report what it printed:

```bash
python3 tools/brand_preview.py vault/projects/<name>/brand/tokens.json
```

It writes `preview.html` next to `tokens.json` (offline, no network) and prints the contrast ratio of every
pair in `pairs`. Report each ratio as printed. If a body text pair is below 4.5:1 (the WCAG AA threshold for
normal text), say so as a fact and ask whether they want to change it; do not change it yourself.

### 6. `manual <name>` (assembles; asks no interview question)

Read `voice.md` (project, then the inherited person file), `dna.md`, `messaging.md`, `design.md` and
`tokens.json`. Build `manual.md` with one section per piece, in that order, each one copying the source's
content unchanged and linking the source file in the sentence that opens the section. A piece whose file does
not exist, or whose field is empty, is marked `empty` with the command that fills it (for example
`empty: run /cf-brand dna <name>`). **Never invent** a line to cover an empty one, and never link a file that
does not exist. The manual is derived: when a source changes, rebuild it; do not edit it by hand. The only
question this mode asks is the yes to save the draft.

### 7. Checking a text against the voice (any time)

```bash
python3 tools/voice_check.py <text.md> --person vault/memory/voice.md [--project <name>]
```

rc 0: no term from `Never say` or `Avoid` was found. rc 1: a term was found; show the line and the term, and
let the user decide what to change. rc 3: `NOT_VERIFIED`, there were no rules to check against; say that and
offer `/cf-brand voice --person`. Never report rc 3 as clean.

### 8. After saving (you)

Every file in `projects/<name>/brand/` links the project root in a sentence
(`[[projects/<name>/instructions|<name>]]`). Then run and report the exit codes:

```bash
python3 tools/hub.py
python3 core/gate.py
python3 core/ring.py --vault vault --gate
```

Close in one short message: what was saved, what is still empty, and the next mode that would fill it. Do not
start writing content with the new voice unless asked.

## Never

- Write about the person or the project something they did not say, or "clean up" their words.
- Save before the "yes".
- Ship or suggest a default color, font, tone or value as if it were theirs.
- Fill an empty field in the manual, or link a file that does not exist.
- Copy the person's voice lines into a project's `voice.md`: the project inherits them.
- Report `NOT_VERIFIED` (rc 3) as "OK".
- Call a network service or an API: everything here is files and two local scripts.
- Write to `vault/notes/`, `patterns.md` or `decisions.md`.
