---
type: brand-design
status: in-progress
---

# Template: how this project should look

Copy this file to `vault/projects/<name>/brand/design.md`. Replace the title with a statement of up to ten words
and delete this paragraph. **This template has no default color, font or size on purpose**: every value comes from
the person, typed or chosen by them. The skill that fills it is described in `.claude/skills/cf-brand/SKILL.md`,
and it is listed in the [[skill-worksheets/_catalog|catalog]].

Project root: link it here with its full path, in the middle of a sentence, for example "this page is about
`[[projects/<name>/instructions|<name>]]`".

## How it should look, in their words

`YYYY-MM-DD | "<their description>"`

## Colors

A color described only in words stays here in their words, with no hex, until they type one or choose one.

| token | hex | used for | source |
|---|---|---|---|
| `<token>` | `<#rrggbb or empty>` | `<what it is for>` | `<typed, or "chose option X">` |

## Type

| role | font | source |
|---|---|---|
| heading | `<font or empty>` | |
| body | `<font or empty>` | |

## Spacing and corners

The spacing scale and the corner radius, as numbers the person gave.

## Three components

Three pieces of interface described in the person's words (for example a button, a card, a header).

## Pairs to check

Text and background token pairs whose contrast `tools/brand_preview.py` prints.

## tokens.json

Saved next to this file as `tokens.json`. It starts with only the name and empty collections; `type`, `space` and
`radius` are added only when the person answers them. A field with no answer is left out, never filled with a default:

```json
{
  "name": "<project name>",
  "colors": {},
  "pairs": []
}
```

The full shape, once answered: `colors` maps a token to `#rrggbb`; `type` has `heading` and `body`; `space` is a list
of numbers; `radius` is a number; `pairs` is a list of `["<fg-token>", "<bg-token>"]`.
