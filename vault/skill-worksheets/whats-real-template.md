---
type: whats-real
status: in-progress
milestone: <demo, delivery, class or launch>
date: YYYY-MM-DD
---

# Template: what is real in this project today

Copy this file to `vault/projects/<name>/whats-real.md`. Replace the title with a statement of up to ten words.
Delete this paragraph. Create it before the milestone, check it after. An item moves up only with proof.

Project root: link it here with its full path, in the middle of a sentence, for example "this page is about
`[[projects/<name>/instructions|<name>]]`". Check the file exists first. The skill that keeps this page is
described in `.claude/skills/whats-real/SKILL.md`.

## Works

Each item has the command that was run, what it printed and the date. No proof, it does not belong here.

| item | command run | output (the relevant line) | date | re-run after the milestone |
|---|---|---|---|---|
| example item | `command` | `what it printed` | YYYY-MM-DD | pending |

## Simulated or demo

What looks like it works and does not: a canned answer, a fixture, a manual step, a number typed by hand.

| item | what is faked | what it would take to be real |
|---|---|---|
| example item | what is hard-coded | the missing piece |

## Unknown

What nobody has checked. Also where items return when a proof fails on re-run, with the date.

| item | what would settle it |
|---|---|
| example item | the command or the person to ask |

## Check after the milestone

- [ ] Every proof in Works was re-run, not reread.
- [ ] Each one that failed went back to Unknown with the date.
- [ ] Nothing was deleted to make the page look better.
- [ ] A dated line was added to the project diary.
