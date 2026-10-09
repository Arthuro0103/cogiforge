# Brand: voice, DNA, messaging and design system, with Claude's help

**Read this first: this organizes what YOU said. It does not create an identity on its own.** Claude asks, you
answer, and the files keep your words with the date. If you have not decided something yet, the file says it is
empty. A brand that comes out of here is only as real as your answers; the tools can check a text against your
rules and preview your colors, but they cannot tell you who you are or what your project should be.

The skill is `cf-brand` (`.claude/skills/cf-brand/SKILL.md`). It works the same way as `cf-onboard` and
`cf-know-my-product`: one question per message, verbatim quotes, nothing deduced, and nothing saved before your
"yes". Everything is files and two local scripts: no API, no network.

## Step by step

1. **Your voice first (once).** Run `/cf-brand voice --person`. Claude asks for a sentence you wrote that sounds
   like you, words you would never use, words you would rather avoid, and pairs of "say it like this, not like
   that". Saved in `vault/memory/voice.md` (team mode: `vault/people/<handle>/memory/voice.md`).
2. **Have a project.** If it does not exist yet, create it with `/cf-new-project <name>`. If you have not written
   the product brief, `/cf-know-my-product <name>` does that; the DNA links it instead of repeating it.
3. **The project's voice, only if it differs.** `/cf-brand voice --project <name>` asks only what changes in this
   project. The file says `inherits:` your voice and keeps just the difference.
4. **DNA.** `/cf-brand dna <name>`: why it exists, for whom, what it is NOT, values, promise.
5. **Messaging.** `/cf-brand messaging <name>`: one sentence, a 30-second pitch, a short bio per platform you name.
6. **Design system.** `/cf-brand design <name>`: colors, type, spacing, corners, three components, and which
   text/background pairs to check. Then look at it: `python3 tools/brand_preview.py vault/projects/<name>/brand/tokens.json`.
7. **Manual.** `/cf-brand manual <name>` asks nothing: it assembles the four pieces into one document, links each
   source, and marks what is still `empty`.
8. **Use it.** Before publishing a text, check it against your rules:
   `python3 tools/voice_check.py <text.md> --person vault/memory/voice.md --project <name>`.

You can stop after any step. A project with only a one-liner is fine.

## What each file is

| file | what it holds | filled by | blank model |
|---|---|---|---|
| `vault/memory/voice.md` | your phrases (dated quotes), words you never say, words you avoid, "say / not" pairs | `voice --person` | `vault/skill-worksheets/brand-voice.md` |
| `vault/projects/<name>/brand/voice.md` | only what this project's voice changes; `inherits:` points to yours | `voice --project` | `vault/skill-worksheets/brand-voice.md` |
| `vault/projects/<name>/brand/dna.md` | purpose, audience, what it is NOT, values, promise | `dna` | `vault/skill-worksheets/brand-dna.md` |
| `vault/projects/<name>/brand/messaging.md` | one-liner, 30-second pitch, bios per platform | `messaging` | `vault/skill-worksheets/brand-messaging.md` |
| `vault/projects/<name>/brand/design.md` | the design system in your words: colors, type, spacing, corners, components, pairs | `design` | `vault/skill-worksheets/brand-design.md` |
| `vault/projects/<name>/brand/tokens.json` | the same values in a format a script can read | `design` | the block at the end of `brand-design.md` |
| `vault/projects/<name>/brand/preview.html` | a single offline page with your palette, type and contrast | `tools/brand_preview.py` | none: generated |
| `vault/projects/<name>/brand/manual.md` | everything above in one document, with a link to each source | `manual` | none: assembled |

### The voice file format

The section names are fixed, because `tools/voice_check.py` reads them:

```
---
type: voice
scope: person            # or: project, plus  inherits: vault/memory/voice.md
---

## Phrases
- YYYY-MM-DD | "a sentence you wrote, word for word"

## Never say
- one word or expression per line

## Avoid
- one word or expression per line

## Pairs
- say: "your way" | not: "the way you would not"
```

`voice_check.py` exits with 0 when no `Never say` or `Avoid` term is in the text, 1 when it finds one (and shows
where), and 3 (`NOT_VERIFIED`) when there are no rules to check against. **3 is not OK**: it means nothing was
checked.

### The tokens format

```json
{
  "name": "<project name>",
  "colors": {"<token>": "#rrggbb"},
  "type": {"heading": "<font>", "body": "<font>"},
  "space": [<numbers>],
  "radius": <number>,
  "pairs": [["<fg-token>", "<bg-token>"]]
}
```

There is **no default palette** in this repo. A field you did not answer is left out. If you describe a color in
words, it stays in `design.md` in your words until you type a hex or choose one of a few candidates Claude shows.
`brand_preview.py` prints the contrast ratio of each pair; 4.5:1 is the usual minimum for body text (WCAG AA).
Claude reports the number and asks; it does not change your colors.

## Asking for help with it

- "Check this post against my voice." (Claude runs `voice_check.py` and shows each hit.)
- "Rewrite this paragraph in my voice." A good answer uses your `Phrases` and `Pairs` as the reference and runs
  the check before showing it.
- "What is still empty in the brand of `<name>`?" (Claude reads the manual or rebuilds it.)
- "Does this tagline match the DNA? Quote the line it matches."

If an answer about your brand does not point to a line in one of these files, ask Claude which line it came from,
or to say it does not know.

## What it will not do

- Invent a value, a tone, a color or a promise you did not give.
- Ship a default design system that looks like yours.
- Save anything without your "yes".
- Fill an empty field in the manual to make it look complete.
- Talk to any online service.

## Related

- [PRODUCT-AND-PAINS.md](PRODUCT-AND-PAINS.md): the product brief that the DNA extends.
- [CONTEXT.md](CONTEXT.md): what loads when, and why the voice file is short.
