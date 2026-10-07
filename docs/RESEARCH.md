# Research with the vault

The rule in one line: **your own notes first, the internet second, and nothing from outside is a fact
until you opened its source.** This guide works with any model; only the "deep research" step below
depends on a website.

> **Websites change.** Menu and feature names were checked on **2026-10-07** against the vendors' own
> help pages. What I could not confirm is marked `[VERIFY: ...]`.

## The loop

1. **State the question as a sentence you could be wrong about.** "What do I already think about
   spaced repetition?" is a question. "Spaced repetition" is a topic.
2. **Search the vault first.** Run `python3 tools/ask.py search "<question>"` (local, no network), or
   use the `ask` skill (`.claude/skills/ask/SKILL.md`, plain text any agent can follow). Read what
   comes back. Note which notes you already have and what they say.
3. **Declare the gap before searching outside.** Write, in the working note, one line per hole:
   "my notes do not cover X". If you cannot name a gap, you do not need the internet yet. This is the
   step people skip, and it is why a research note ends up repeating what the vault already said.
4. **Search outside only for the declared gaps.** Open every source yourself.
5. **Mark every outside claim `[VERIFY]` until you checked it** against the open source: the page
   exists, says what you wrote, and is from who you think. Use the form
   `[VERIFY: what is missing]`. A claim that stays `[VERIFY]` is allowed in a draft and never in a
   note you present as finished.
6. **Name the target and write the diff there** (`project::`, `article::`, `question::`, `task::` or
   `none`), in the same commit as the note.

## Citations that hold up

- Every outside claim carries its URL, the title of the page and the **date you opened it**.
- Prefer the primary source (the paper, the official docs, the law) over the page that talks about it.
- A summary written by a model is not a source. Its links are leads: open them. Models invent links
  and quotes that look right.
- Quote sparingly and exactly, and keep your own words apart from the source's.
- What the vault already says is cited with a full-path link in the body, for example
  `[[notes/learning/some-note|my earlier note]]`. `python3 tools/ask.py cite <draft.md>` checks that
  every such link points to something that exists.

## Deep research on a website

All three major assistants have a mode that browses many sources for several minutes and returns a
report with sources. It is a **fast way to find leads**, not a source of facts: the report is outside
material and every claim in it starts as `[VERIFY]`.

| Site | How to start it (per the vendor's help page, checked 2026-10-07) | Needs |
|---|---|---|
| Claude | click the **+** button at the bottom left of the chat, then **Research** (the help page calls it "research") | a paid plan and web search turned on |
| ChatGPT | type `/deepresearch`, or choose **Deep research** in the **+** tools menu or in the sidebar | `[VERIFY: which plans include it and the monthly limit; the page I read did not settle it, checked 2026-10-07]` |
| Gemini | at gemini.google.com click **Add Files**, then **Deep Research**; it usually takes 5 to 10 minutes | being 18 or older and signed in |

Sources: [Claude](https://support.claude.com/en/articles/11088861-use-research-on-claude),
[ChatGPT](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt),
[Gemini](https://support.google.com/gemini/answer/15719111).

Tips that work on all three:

- Give the question **and what you already know** (paste your notes' conclusions from step 2), and
  say what you want left out. A good prompt names the gap from step 3.
- Ask for the sources as full URLs next to each claim, and for what it could **not** find.
- ChatGPT shows a research plan you can edit before it starts, and its help page says completed reports
  can be downloaded as Markdown, Word or PDF. For the other two, copy the text out or use the site's
  own export: `[VERIFY: how to save a finished Claude Research or Gemini Deep Research report as a file; I did not find an official page, checked 2026-10-07]`.

## Save the result in `inbox/` with its provenance

Create `vault/inbox/research-<topic>.md` (not in `notes/`: it is raw until you triaged it) and start with:

```
---
type: research-capture
source: claude | chatgpt | gemini
tool: <the mode you used, as the site names it>
url: <link to the chat or report, if the site gives one>
date: 2026-10-07
question: <the sentence from step 1>
status: unverified
---
```

Then paste the report below it, unedited. Every claim inside is `[VERIFY]` by default. Two things to keep:
the **date** (the web moves) and the **URL** of each source the report cites.

## Triage into `notes/`, with a target

Work through the capture claim by claim:

1. Open the source. If it supports the claim, write the claim **in your own words** in the target file
   (a project root, an article, a note) with the URL and the date, and remove its `[VERIFY]`.
2. If the source does not exist or does not say that, delete the claim. Write one line in the capture:
   "dropped: source did not support it".
3. If you did not get to it, leave `[VERIFY]` in place.
4. When nothing is left to triage, mark the capture `status: triaged` and name the target it fed. If it
   fed nothing, the target is `none`, and that is a fine answer.

`python3 core/gate.py` must stay clean: use full-path links, put them in the body, and do not add a
`## Connections` block.

## In a group or a school

Everyone can read the capture, and everyone can be misled by an unverified claim in it. Keep captures
`status: unverified` out of shared notes, and make `[VERIFY]` a review blocker: a note with one left
is not ready to merge.
