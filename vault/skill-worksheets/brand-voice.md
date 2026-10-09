---
type: voice
scope: person
---

# Template: the voice rules of a person or a project

Copy this file to `vault/memory/voice.md` for a person (team mode: `vault/people/<handle>/memory/voice.md`), or to
`vault/projects/<name>/brand/voice.md` for a project. Replace the title with a statement of up to ten words and
delete this paragraph. The skill that fills it is described in `.claude/skills/cf-brand/SKILL.md`, and it is
listed in the [[skill-worksheets/_catalog|catalog]].

For a project, change the frontmatter to `scope: project` and add `inherits: vault/memory/voice.md` (or the team
path). A project file keeps only what **differs** from the person's: what is inherited stays in the person's file.

The four section names below are read by `tools/voice_check.py`. Keep them exactly as written. A section with no
answer stays empty under its heading: an empty section is no rule, never a guess.

Line formats, one per line, each one in the person's own words:

- under Phrases: `- YYYY-MM-DD | "<their exact words>"`
- under Never say and Avoid: `- <one word or expression>`
- under Pairs: `- say: "<their way>" | not: "<the way they would not>"`

## Phrases

## Never say

## Avoid

## Pairs
