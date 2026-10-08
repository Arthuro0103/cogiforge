---
name: cf-ask
description: Answers a question about the user's own workbench using ONLY what the notes say, and cites every claim with [[path#Heading]] that a script then checks exists. Rewrites the question into 3-5 short queries, retrieves passages with tools/ask.py (local BM25, no API, no network), discards the irrelevant ones saying why, answers from what is left. If no passage supports the answer it says "the vault does not cover this". TRIGGERS - "ask the vault", "what do my notes say about X", "what do I know about X", "/cf-ask <question>". Do NOT trigger for questions about code or the world outside the vault, for writing or editing notes, for deciding between paths, nor to get to know the user (that is onboard). OPTIONAL MODE - "/cf-ask --try-first <question>" (or "let me try first"): it asks for the user's own attempt before showing the answer.
---

# cf-ask: answer from the notes, and prove the citations exist

## Why it exists

A model that answers from memory about a person's notes invents plausible ones. The fix is to make the
answer carry its sources, and to have a script (not the model) check that each source is real.
You are the intelligence here: `tools/ask.py` only retrieves and verifies. No API, no network.

## The rules

1. **Answer only from retrieved passages.** If you did not read it in a passage, you do not say it.
2. **Never write about the user what they did not say** (rule 2 of the repo). A note that says something
   about the user may be quoted as what the note says, never turned into a conclusion about them.
3. **Every claim is followed by `[[path#Heading]]`**, copied from the `search` output, never typed from memory.
4. **Run `cite` before delivering.** If it exits 1, remove or fix the failing citation and run it again.
   If it exits 3 (`NOT_VERIFIED`), say the citations could not be checked; do not call the answer verified.
5. **No passage supports it, no answer.** Say "the vault does not cover this", and what you searched for.
6. **Read-only.** This skill writes nothing in `vault/`. The draft answer goes in a scratch file outside the repo.

> Talk to the user in the language the user writes in. Never translate a quote.

## Optional mode: try first (`--try-first`)

**Off by default.** When the user does not ask for it, nothing below changes anything above.

Trigger: the user writes `/cf-ask --try-first <question>`, or says "let me try first" / "me deixa tentar primeiro".

Why it exists: reading an answer you did not first try to recall feels like learning and teaches less than trying first (retrieval practice, in `docs/`). Use it for questions the user wants to *learn*, not to look up.

1. Do steps 1 to 3 (rewrite, search, read and discard) **silently**. Do NOT show a passage, a title or a hint yet.
2. Ask once: "Write what you remember, in your own words. A few lines is enough. Optional: how sure are you, 0 to 100?" Then **STOP and wait** for the reply.
3. "I do not remember" or "skip" counts as an attempt. Go on, without comment.
4. Do steps 4 to 6 as usual (answer from the kept passages, run `cite`, deliver). Rules 1 to 6 still hold.
5. After the delivered answer, add a short comparison, **built only from the answer you just checked**:
   - **Matched:** what the user said that the passages support, with the citation.
   - **Missing from your attempt:** what the passages say that the user did not mention, with the citation.
   - **Not in the vault:** what the user said that no retrieved passage covers. Say "not in the vault", never "wrong": the vault may simply not have it.
   - If the user gave a confidence, repeat it next to the result in one line (for example: "you said 70; you matched 2 of 3 points"). Do not grade the person.
6. If the vault does not cover the question (rule 5), say so right after the attempt and skip the comparison.
7. Read-only, as always: the comparison stays in the chat.

## The steps

### 1. Rewrite the question (you)

Turn it into 3-5 short queries: the key terms, a synonym, the same idea in the other language (Portuguese
and English both work; accents do not matter). Short beats long: BM25 matches words, not meaning.

### 2. Search, once per query (command)

```bash
python3 tools/ask.py search "<query>" --top 8
python3 tools/ask.py search "<query>" --top 8 --links    # also follows [[wikilinks]] one hop, marked "via link"
```

Merge the results by id. A passage found by several queries is more likely relevant. Each result shows its
id (the citation), the path `note > section > subsection`, and the text.

### 3. Read and discard (you)

Read the passages. For each one you drop, write one line saying why (off-topic, outdated, only shares a
word). Keep the discard list; show it if the user asks. If a `via link` passage is what answers it, keep it.

### 4. Answer (you)

Write the answer from the kept passages only, short, citing after each claim. Where passages disagree, show
both with their citations and do not pick one.

### 5. Check the citations (command)

```bash
python3 tools/ask.py cite <answer-file>        # rc=0 all exist, rc=1 some do not, rc=3 NOT_VERIFIED
```

Fix until rc=0. `cite` proves the citations **exist**, not that they say what you claim: that part is yours,
so re-read each cited passage against its claim.

### 6. Deliver (you)

The answer, then one line: `citations checked: <n>, rc=<rc>`. If nothing supported it:
*"The vault does not cover this."* plus the queries you tried.

## Never

- Cite a passage you did not read in the `search` output.
- Fill a gap with general knowledge without marking it clearly as not from the vault.
- Deliver an answer whose `cite` run failed or was not run.
- Write a conclusion about the user that no note states.
- In `--try-first` mode: show or paraphrase a retrieved passage before the user's attempt, or call an attempt "wrong".
